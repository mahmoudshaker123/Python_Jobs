from django.core.management.base import BaseCommand
from django.db import transaction

from jobs.job_sources import SourceUnavailable
from jobs.models import Startup
from jobs.startup_sources import scrape_techny_startups


class Command(BaseCommand):
    help = 'Collect the public MENA startup directory from Techny HTML pages.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=80)
        parser.add_argument('--delay', type=float, default=0.2)

    def handle(self, *args, **options):
        try:
            rows = scrape_techny_startups(
                limit=max(1, options['limit']),
                delay=max(0, options['delay']),
                output=lambda message: self.stderr.write(self.style.WARNING(message)),
            )
        except SourceUnavailable as exc:
            self.stderr.write(self.style.WARNING(
                f'Startups were not updated ({exc}); existing records were preserved.'
            ))
            return

        created_count = updated_count = 0
        with transaction.atomic():
            for row in rows:
                defaults = row.copy()
                defaults.pop('slug', None)
                _, created = Startup.objects.update_or_create(
                    slug=row['slug'],
                    defaults=defaults,
                )
                created_count += int(created)
                updated_count += int(not created)
        self.stdout.write(self.style.SUCCESS(
            f'Techny startups: {created_count} new, {updated_count} updated.'
        ))
