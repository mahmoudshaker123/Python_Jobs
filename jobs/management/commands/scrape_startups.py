from django.core.management.base import BaseCommand, CommandError

from jobs.startup_sync import run_startup_update


class Command(BaseCommand):
    help = 'Collect the public MENA startup directory from Techny HTML pages.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=80)
        parser.add_argument('--delay', type=float, default=0.2)
        parser.add_argument('--trigger', default='manual')

    def handle(self, *args, **options):
        try:
            run = run_startup_update(
                trigger=options['trigger'], limit=options['limit'], delay=options['delay'],
            )
        except Exception as exc:
            raise CommandError(f'Startup update failed: {exc}') from exc
        self.stdout.write(run.output or f'Startup update {run.status}.')
