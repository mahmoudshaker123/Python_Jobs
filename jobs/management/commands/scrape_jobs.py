from django.core.management.base import BaseCommand
from django.db import transaction

from jobs.job_sources import SCRAPERS, SourceUnavailable, is_allowed_linkedin_location
from jobs.classification import classify_job
from jobs.models import Company, Job


class Command(BaseCommand):
    help = 'Collect technology and ERP jobs from all configured public sources.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sources',
            default=','.join(SCRAPERS),
            help=f"Comma-separated sources: {','.join(SCRAPERS)}",
        )
        parser.add_argument('--limit', type=int, default=40, help='Maximum jobs per source.')
        parser.add_argument('--delay', type=float, default=0.2, help='Delay between public page requests.')
        parser.add_argument(
            '--keep-stale',
            action='store_true',
            help='Do not remove old records for sources that update successfully.',
        )

    def handle(self, *args, **options):
        requested = [value.strip().lower() for value in options['sources'].split(',') if value.strip()]
        unknown = sorted(set(requested) - set(SCRAPERS))
        if unknown:
            self.stderr.write(self.style.ERROR(f"Unknown sources: {', '.join(unknown)}"))
            return

        totals = {'new': 0, 'updated': 0, 'removed': 0, 'sources': 0}
        for key in requested:
            source_name, scraper = SCRAPERS[key]
            self.stdout.write(f'Collecting {source_name} jobs...')
            try:
                jobs = scraper(
                    limit=max(1, options['limit']),
                    delay=max(0, options['delay']),
                    output=lambda message: self.stderr.write(self.style.WARNING(message)),
                )
            except SourceUnavailable as exc:
                self.stderr.write(self.style.WARNING(
                    f'{source_name} was not updated ({exc}); existing {source_name} jobs were preserved.'
                ))
                continue
            if not jobs:
                self.stderr.write(self.style.WARNING(
                    f'{source_name} returned no jobs; existing records were preserved.'
                ))
                continue

            source_urls = set()
            created_count = updated_count = removed_count = 0
            with transaction.atomic():
                for data in jobs:
                    category, skills = classify_job(
                        data.get('title'),
                        data.get('description'),
                        data.get('requirements'),
                    )
                    company, _ = Company.objects.get_or_create(
                        name=data.get('company') or 'Company not disclosed',
                        defaults={'location': data.get('location') or '', 'description': ''},
                    )
                    defaults = {
                        'title': data['title'][:255],
                        'company': company,
                        'location': (data.get('location') or 'Location not specified')[:255],
                        'description': data.get('description') or 'See the original job post.',
                        'requirement': data.get('requirements') or 'See the original job post.',
                        'job_type': data.get('job_type') or 'Full-time',
                        'source': source_name,
                        'category': data.get('category') or category,
                        'skills': data.get('skills') or skills,
                    }
                    if data.get('posted_at'):
                        defaults['posted_at'] = data['posted_at']
                    job, created = Job.objects.update_or_create(
                        job_url=data['job_url'], defaults=defaults,
                    )
                    source_urls.add(job.job_url)
                    created_count += int(created)
                    updated_count += int(not created)
                if not options['keep_stale']:
                    stale = Job.objects.filter(source=source_name).exclude(job_url__in=source_urls)
                    removed_count = stale.count()
                    stale.delete()
                if source_name == 'LinkedIn':
                    disallowed_ids = [
                        job.pk
                        for job in Job.objects.filter(source='LinkedIn').only('pk', 'location')
                        if not is_allowed_linkedin_location(job.location)
                    ]
                    if disallowed_ids:
                        removed_count += len(disallowed_ids)
                        Job.objects.filter(pk__in=disallowed_ids).delete()

            totals['new'] += created_count
            totals['updated'] += updated_count
            totals['removed'] += removed_count
            totals['sources'] += 1
            self.stdout.write(self.style.SUCCESS(
                f'{source_name}: {created_count} new, {updated_count} updated, {removed_count} stale removed.'
            ))

        self.stdout.write(self.style.SUCCESS(
            f"Finished {totals['sources']} source(s): {totals['new']} new, "
            f"{totals['updated']} updated, {totals['removed']} removed."
        ))
