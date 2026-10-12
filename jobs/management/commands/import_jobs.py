import csv
from email.utils import parsedate_to_datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from jobs.models import Company, Job


class Command(BaseCommand):
    help = 'Import or update jobs from a Wuzzuf CSV export.'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', help='Path to the CSV file')
        parser.add_argument(
            '--replace-source',
            help='Delete records from this source when their URL is absent from the CSV.',
        )

    @staticmethod
    def value(row, name, default=''):
        return (row.get(name) or row.get(name.lower()) or default).strip()

    def handle(self, *args, **options):
        imported = updated = skipped = 0
        imported_urls = set()
        try:
            csv_handle = open(options['csv_file'], encoding='utf-8-sig', newline='')
        except OSError as exc:
            raise CommandError(f'Could not open CSV file: {exc}') from exc

        with csv_handle, transaction.atomic():
            for row in csv.DictReader(csv_handle):
                title = self.value(row, 'Title')
                job_url = self.value(row, 'Link') or self.value(row, 'job_url')
                if not title or not job_url:
                    skipped += 1
                    continue

                company_name = self.value(row, 'Company', 'Unknown company') or 'Unknown company'
                location = self.value(row, 'Location', 'Flexible') or 'Flexible'
                company, _ = Company.objects.get_or_create(
                    name=company_name,
                    defaults={'location': location, 'description': ''},
                )
                defaults = {
                    'title': title,
                    'company': company,
                    'location': location,
                    'description': self.value(row, 'Job Description', 'Description available on the original job post.'),
                    'requirement': self.value(row, 'Job Requirements', 'See the original job post for full requirements.'),
                    'job_type': self.value(row, 'Job Type', 'Full-time') or 'Full-time',
                    'source': self.value(row, 'Source', options.get('replace_source') or 'Wuzzuf'),
                }
                date_posted = self.value(row, 'Date Posted')
                if date_posted:
                    try:
                        posted_at = parsedate_to_datetime(date_posted)
                        defaults['posted_at'] = (
                            timezone.make_aware(posted_at)
                            if timezone.is_naive(posted_at)
                            else posted_at
                        )
                    except (TypeError, ValueError, OverflowError):
                        pass
                _, created = Job.objects.update_or_create(job_url=job_url, defaults=defaults)
                imported_urls.add(job_url)
                if created:
                    imported += 1
                else:
                    updated += 1

            removed = 0
            replace_source = options.get('replace_source')
            if replace_source and imported_urls:
                stale_jobs = Job.objects.filter(source=replace_source).exclude(job_url__in=imported_urls)
                removed = stale_jobs.count()
                stale_jobs.delete()

        self.stdout.write(self.style.SUCCESS(
            f'Import complete: {imported} new, {updated} updated, '
            f'{skipped} skipped, {removed} stale removed.'
        ))
