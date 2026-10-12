from datetime import timedelta
from io import StringIO

from django.conf import settings
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone

from .models import Job, JobSyncRun, JobSyncState


def _claim_sync(trigger):
    now = timezone.now()
    stale_before = now - timedelta(hours=4)
    with transaction.atomic():
        state, _ = JobSyncState.objects.select_for_update().get_or_create(name='jobs')
        if state.is_running and state.started_at and state.started_at > stale_before:
            run = JobSyncRun.objects.create(
                status='skipped',
                trigger=trigger,
                started_at=now,
                finished_at=now,
                output='Another job update is already running.',
            )
            return state, run, False
        state.is_running = True
        state.started_at = now
        state.finished_at = None
        state.save(update_fields=('is_running', 'started_at', 'finished_at'))
        run = JobSyncRun.objects.create(status='running', trigger=trigger, started_at=now)
    return state, run, True


def run_job_update(trigger='manual', *, sources=None, limit=None, delay=None):
    state, run, claimed = _claim_sync(trigger)
    if not claimed:
        return run

    stdout = StringIO()
    stderr = StringIO()
    try:
        command_options = {
            'limit': limit or settings.JOB_SYNC_LIMIT,
            'delay': settings.JOB_SYNC_DELAY if delay is None else delay,
            'stdout': stdout,
            'stderr': stderr,
        }
        if sources:
            command_options['sources'] = sources
        scrape_error = None
        try:
            call_command('scrape_jobs', **command_options)
        except Exception as exc:
            scrape_error = exc
        cutoff = timezone.now() - timedelta(days=settings.JOB_RETENTION_DAYS)
        expired = Job.objects.filter(posted_at__lt=cutoff)
        removed = expired.count()
        expired.delete()
        run.jobs_removed = removed

        if scrape_error:
            raise scrape_error

        run.status = 'success'
        run.output = (stdout.getvalue() + '\n' + stderr.getvalue()).strip()[-12000:]
        return run
    except Exception as exc:
        run.status = 'failed'
        run.error = str(exc)[:4000]
        run.output = (stdout.getvalue() + '\n' + stderr.getvalue()).strip()[-12000:]
        raise
    finally:
        finished_at = timezone.now()
        run.finished_at = finished_at
        run.save(update_fields=('status', 'finished_at', 'jobs_removed', 'output', 'error'))
        JobSyncState.objects.filter(pk=state.pk).update(
            is_running=False,
            finished_at=finished_at,
        )
