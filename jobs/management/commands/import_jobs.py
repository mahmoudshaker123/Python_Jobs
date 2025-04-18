import csv
from django.core.management.base import BaseCommand
from django.db import transaction
from jobs.models import Job, Company
import re

class Command(BaseCommand):
    help = 'Import jobs from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')

    def extract_company_name(self, url):
        # Extract company name from URL
        # Example URL: https://wuzzuf.net/jobs/p/bBVD1SDdlEN8-Data-Engineer-HYVE-Technology-Consulting-Cairo-Egypt
        match = re.search(r'-(.*?)-(Cairo|Giza)-Egypt$', url)
        if match:
            # Split by '-' and take the last part which should be the company name
            parts = match.group(1).split('-')
            # Remove job title parts (usually the first few parts)
            company_parts = parts[-3:]  # Take last 3 parts which usually contain company name
            
            # Remove common job-related words
            job_words = {'developer', 'engineer', 'administrator', 'manager', 'specialist', 'system'}
            company_name = ' '.join(part for part in company_parts if part.lower() not in job_words)
            
            return company_name if company_name else "Unknown Company"
        return "Unknown Company"

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        success_count = 0
        error_count = 0
        skipped_count = 0

        try:
            with open(csv_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                for row in reader:
                    try:
                        with transaction.atomic():
                            # Extract company name from URL if Company field is empty
                            company_name = row['Company'] if row['Company'] else self.extract_company_name(row['Link'])
                            
                            # Get or create company
                            company, created = Company.objects.get_or_create(
                                name=company_name,
                                defaults={
                                    'location': row['Location'],
                                    'description': f"Company from {row['Location']}"
                                }
                            )

                            # Check if job already exists
                            if Job.objects.filter(title=row['Title'], company=company).exists():
                                self.stdout.write(
                                    self.style.WARNING(f'Skipping duplicate job: {row["Title"]} at {company.name}')
                                )
                                skipped_count += 1
                                continue

                            # Create new job
                            Job.objects.create(
                                title=row['Title'],
                                company=company,
                                location=row['Location'],
                                description=row['Job Description'],
                                requirement=row['Job Requirements'],
                                job_url=row['Link']
                            )
                            success_count += 1
                            self.stdout.write(
                                self.style.SUCCESS(f'Successfully imported job: {row["Title"]} at {company.name}')
                            )

                    except Exception as e:
                        error_count += 1
                        self.stdout.write(
                            self.style.ERROR(f'Error importing job {row["Title"]}: {str(e)}')
                        )

        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(f'CSV file not found: {csv_file}')
            )
            return

        # Print summary
        self.stdout.write(self.style.SUCCESS(
            f'\nImport completed!\n'
            f'Successfully imported: {success_count}\n'
            f'Skipped duplicates: {skipped_count}\n'
            f'Errors: {error_count}'
        )) 