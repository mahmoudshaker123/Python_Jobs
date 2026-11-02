from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .job_sources import SourceUnavailable
from .models import Startup, StartupSyncRun, StartupSyncState
from .startup_sources import scrape_techny_startups


def run_startup_update(trigger='manual', *, limit=80, delay=0.2):
    now = timezone.now()
    stale_before = now - timedelta(hours=4)
    with transaction.atomic():
        StartupSyncState.objects.get_or_create(name='startups')
        state = StartupSyncState.objects.select_for_update().get(name='startups')
        if state.is_running and state.started_at and state.started_at > stale_before:
            return StartupSyncRun.objects.create(
                status='skipped', trigger=trigger, started_at=now,
                finished_at=now, output='Another startup update is already running.',
            )
        state.is_running = True
        state.started_at = now
        state.finished_at = None
        state.save(update_fields=('is_running', 'started_at', 'finished_at'))
        run = StartupSyncRun.objects.create(status='running', trigger=trigger, started_at=now)

    try:
        rows = scrape_techny_startups(limit=max(1, limit), delay=max(0, delay))
        if not rows:
            raise SourceUnavailable('Startup source returned no listings; existing data was preserved.')

        created_count = updated_count = 0
        with transaction.atomic():
            for row in rows:
                defaults = row.copy()
                defaults.pop('slug', None)
                _, created = Startup.objects.update_or_create(slug=row['slug'], defaults=defaults)
                created_count += int(created)
                updated_count += int(not created)
        run.status = 'success'
        run.startups_seen = len(rows)
        run.startups_created = created_count
        run.startups_updated = updated_count
        run.output = f'Techny startups: {created_count} new, {updated_count} updated.'
        return run
    except Exception as exc:
        run.status = 'failed'
        run.error = str(exc)[:4000]
        run.output = 'Existing startup records were preserved.'
        raise
    finally:
        finished_at = timezone.now()
        run.finished_at = finished_at
        run.save(update_fields=(
            'status', 'finished_at', 'startups_seen', 'startups_created',
            'startups_updated', 'output', 'error',
        ))
        StartupSyncState.objects.filter(pk=state.pk).update(
            is_running=False, finished_at=finished_at,
        )
