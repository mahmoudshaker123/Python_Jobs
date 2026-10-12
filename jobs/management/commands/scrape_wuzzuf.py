import csv
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand, CommandError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from jobs.wuzzuf import extract_job


class Command(BaseCommand):
    help = 'Scrape validated Python and Odoo jobs from Wuzzuf.'

    SEARCHES = (
        'https://wuzzuf.net/search/jobs/?q=python&a=hpb',
        'https://wuzzuf.net/search/jobs/?q=odoo%20developer&a=hpb',
    )
    CSV_FIELDS = (
        'Title', 'Company', 'Location', 'Link', 'Job Description',
        'Job Requirements', 'Experience', 'Salary', 'Job Type', 'Date Posted',
    )

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=50, help='Maximum jobs to collect.')
        parser.add_argument('--delay', type=float, default=0.4, help='Delay between detail requests.')

    @staticmethod
    def session():
        session = requests.Session()
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=0.7,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=('GET',),
        )
        session.mount('https://', HTTPAdapter(max_retries=retry))
        session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.8',
            'Referer': 'https://wuzzuf.net/jobs/egypt',
        })
        return session

    def handle(self, *args, **options):
        limit = max(1, options['limit'])
        delay = max(0, options['delay'])
        csv_file = Path(__file__).resolve().parents[3] / 'temp' / 'all_jobs.csv'
        csv_file.parent.mkdir(parents=True, exist_ok=True)

        collected = []
        seen_urls = set()
        session = self.session()
        try:
            session.get('https://wuzzuf.net/jobs/egypt', timeout=20)
        except requests.RequestException:
            pass

        for base_url in self.SEARCHES:
            page = 0
            while len(collected) < limit:
                search_url = base_url if page == 0 else f'{base_url}&start={page}'
                self.stdout.write(f'Loading search page {page + 1}: {search_url}')
                try:
                    response = session.get(search_url, timeout=25)
                    response.raise_for_status()
                    response.encoding = 'utf-8'
                except requests.RequestException as exc:
                    self.stderr.write(self.style.WARNING(f'Search page skipped: {exc}'))
                    break

                soup = BeautifulSoup(response.text, 'html.parser')
                links = []
                for anchor in soup.find_all('a', href=lambda value: value and '/jobs/p/' in value):
                    job_url = urljoin('https://wuzzuf.net', anchor['href']).split('?')[0]
                    if job_url not in seen_urls:
                        links.append((job_url, anchor.get_text(' ', strip=True)))
                        seen_urls.add(job_url)

                if not links:
                    break

                added_on_page = 0
                for job_url, fallback_title in links:
                    if len(collected) >= limit:
                        break
                    try:
                        detail = session.get(job_url, timeout=25)
                        detail.raise_for_status()
                        detail.encoding = 'utf-8'
                        job = extract_job(detail.text, job_url, fallback_title)
                    except requests.RequestException as exc:
                        self.stderr.write(self.style.WARNING(f'Detail skipped ({job_url}): {exc}'))
                        continue

                    if not job:
                        self.stderr.write(self.style.WARNING(f'No JobPosting data; skipped: {job_url}'))
                        continue

                    collected.append(job)
                    added_on_page += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"[{len(collected)}/{limit}] {job['title']} | {job['company']} | "
                        f"{job['location']} | {job['job_type']}"
                    ))
                    if delay:
                        time.sleep(delay)

                if added_on_page == 0:
                    break
                page += 1

        if not collected:
            raise CommandError('No valid jobs were collected; the existing CSV was left unchanged.')

        temporary_file = csv_file.with_suffix('.csv.tmp')
        with temporary_file.open('w', newline='', encoding='utf-8-sig') as handle:
            writer = csv.DictWriter(handle, fieldnames=self.CSV_FIELDS, lineterminator='\n')
            writer.writeheader()
            for job in collected:
                writer.writerow({
                    'Title': job['title'],
                    'Company': job['company'],
                    'Location': job['location'],
                    'Link': job['job_url'],
                    'Job Description': job['description'],
                    'Job Requirements': job['requirements'],
                    'Experience': job['experience'],
                    'Salary': job['salary'],
                    'Job Type': job['job_type'],
                    'Date Posted': job['date_posted'],
                })
        temporary_file.replace(csv_file)
        self.stdout.write(self.style.SUCCESS(f'Saved {len(collected)} validated jobs to {csv_file}'))
