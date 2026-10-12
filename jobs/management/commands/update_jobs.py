from django.core.management.base import BaseCommand

from jobs.sync import run_job_update


class Command(BaseCommand):
    help = 'Update jobs from all configured public sources.'

    def add_arguments(self, parser):
        parser.add_argument('--sources', default=None)
        parser.add_argument('--limit', type=int, default=None)
        parser.add_argument('--delay', type=float, default=None)

    def handle(self, *args, **options):
        run = run_job_update(
            trigger='management-command',
            sources=options['sources'],
            limit=options['limit'],
            delay=options['delay'],
        )
        self.stdout.write(self.style.SUCCESS(
            f'Job update {run.status}. Expired jobs removed: {run.jobs_removed}.'
        ))
