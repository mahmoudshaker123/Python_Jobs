import re
import time
from datetime import timedelta
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from django.utils import timezone
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .wuzzuf import clean_text, extract_job


class SourceUnavailable(RuntimeError):
    """Raised when a source blocks or cannot serve a usable jobs page."""


def build_session(referer=None):
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.8,
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
        'Accept-Language': 'en-US,en;q=0.8,ar;q=0.6',
    })
    if referer:
        session.headers['Referer'] = referer
    return session


def fetch_html(session, url, timeout=25):
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or 'utf-8'
    text = response.text
    if 'cf-chl-' in text or 'Just a moment...' in text:
        raise SourceUnavailable(f'{urlparse(url).netloc} requested a browser challenge')
    return text


def parse_relative_date(value):
    text = clean_text(value).lower()
    now = timezone.now()
    if any(term in text for term in ('just now', 'today', 'الآن', 'اليوم', 'دقيقة')):
        return now
    match = re.search(r'(\d+)\s*(hour|day|week|month|ساعة|ساعات|يوم|أيام|ايام|أسبوع|اسبوع|أسابيع|اسابيع|شهر|أشهر|اشهر)', text)
    if not match:
        return now
    amount = int(match.group(1))
    unit = match.group(2)
    if unit in ('hour', 'ساعة', 'ساعات'):
        return now - timedelta(hours=amount)
    if unit in ('week', 'أسبوع', 'اسبوع', 'أسابيع', 'اسابيع'):
        return now - timedelta(weeks=amount)
    if unit in ('month', 'شهر', 'أشهر', 'اشهر'):
        return now - timedelta(days=amount * 30)
    return now - timedelta(days=amount)


def scrape_wuzzuf(limit=40, delay=0.2, output=None):
    searches = (
        ('Python', 'https://wuzzuf.net/search/jobs/?q=python&a=hpb'),
        ('Odoo', 'https://wuzzuf.net/search/jobs/?q=odoo%20developer&a=hpb'),
    )
    session = build_session('https://wuzzuf.net/jobs/egypt')
    jobs = []
    seen = set()
    quota = max(1, limit // len(searches))

    for query_name, base_url in searches:
        query_jobs = []
        page = 0
        query_limit = quota if query_name != searches[-1][0] else limit - len(jobs)
        while len(query_jobs) < query_limit:
            search_url = base_url if page == 0 else f'{base_url}&start={page}'
            try:
                html = fetch_html(session, search_url)
            except (requests.RequestException, SourceUnavailable) as exc:
                if output:
                    output(f'Wuzzuf {query_name} page skipped: {exc}')
                break
            soup = BeautifulSoup(html, 'html.parser')
            links = []
            for anchor in soup.find_all('a', href=lambda value: value and '/jobs/p/' in value):
                url = urljoin('https://wuzzuf.net', anchor['href']).split('?')[0]
                if url not in seen:
                    seen.add(url)
                    links.append((url, anchor.get_text(' ', strip=True)))
            if not links:
                break
            added = 0
            for url, fallback_title in links:
                if len(query_jobs) >= query_limit:
                    break
                try:
                    job = extract_job(fetch_html(session, url), url, fallback_title)
                except (requests.RequestException, SourceUnavailable):
                    continue
                if job:
                    job['source'] = 'Wuzzuf'
                    query_jobs.append(job)
                    added += 1
                    if delay:
                        time.sleep(delay)
            if not added:
                break
            page += 1
        jobs.extend(query_jobs)
    return jobs[:limit]


_BAYT_JOB_URL = re.compile(r'^/en/[^/]+/jobs/.+-\d+/?$')


def parse_bayt_listing(html, base_url='https://www.bayt.com'):
    soup = BeautifulSoup(html, 'html.parser')
    jobs = []
    seen = set()
    for anchor in soup.find_all('a', href=lambda value: value and _BAYT_JOB_URL.match(value)):
        url = urljoin(base_url, anchor['href'].split('?')[0])
        title = clean_text(anchor.get_text(' ', strip=True))
        if url in seen or not title or title.lower() in {'easy apply', 'apply now'}:
            continue
        seen.add(url)

        card = anchor
        for parent in anchor.parents:
            if parent.name in {'li', 'article'}:
                card = parent
                break
            if parent.name == 'body':
                break
        strings = [clean_text(value) for value in card.stripped_strings if clean_text(value)]
        summary = next((value[8:].strip() for value in strings if value.lower().startswith('summary:')), '')
        link_texts = [clean_text(link.get_text(' ', strip=True)) for link in card.find_all('a')]
        company = next(
            (value for value in link_texts if value and value != title and value.lower() not in {'easy apply', 'apply now'}),
            'Company not disclosed',
        )
        location = next(
            (value for value in strings if len(value) < 80 and re.search(r'\b(remote|uae|egypt|saudi arabia|qatar|kuwait|jordan|usa|india|pakistan|lebanon|morocco|iraq|bahrain|oman|tunisia|algeria)\b', value, re.I)),
            'Location not specified',
        )
        date_text = next((value for value in strings if re.search(r'\b(day|hour|week|month)s? ago\b', value, re.I)), '')
        job_type = 'Contract' if any('contract' in value.lower() for value in strings) else 'Full-time'
        jobs.append({
            'title': title,
            'company': company,
            'location': location[:120],
            'job_url': url,
            'description': summary or 'Description available on the original Bayt job post.',
            'requirements': 'See the original Bayt job post for full requirements.',
            'job_type': job_type,
            'posted_at': parse_relative_date(date_text),
            'source': 'Bayt',
        })
    return jobs


def scrape_bayt(limit=40, delay=0.2, output=None):
    searches = (
        'https://www.bayt.com/en/international/jobs/python-jobs/',
        'https://www.bayt.com/en/international/jobs/odoo-jobs/',
    )
    session = build_session('https://www.bayt.com/')
    jobs = []
    seen = set()
    per_query = max(1, limit // len(searches))
    successful_pages = 0
    for search_url in searches:
        try:
            parsed = parse_bayt_listing(fetch_html(session, search_url))
            successful_pages += 1
        except (requests.RequestException, SourceUnavailable) as exc:
            if output:
                output(f'Bayt page skipped: {exc}')
            continue
        for job in parsed:
            if job['job_url'] not in seen and len([j for j in jobs if j.get('_query') == search_url]) < per_query:
                seen.add(job['job_url'])
                job['_query'] = search_url
                jobs.append(job)
        if delay:
            time.sleep(delay)
    if not successful_pages:
        raise SourceUnavailable('Bayt did not return an accessible jobs page')
    for job in jobs:
        job.pop('_query', None)
    return jobs[:limit]


MOURJAN_REGIONS = {
    'ae': 'United Arab Emirates', 'sa': 'Saudi Arabia', 'eg': 'Egypt',
    'kw': 'Kuwait', 'jo': 'Jordan', 'qa': 'Qatar', 'bh': 'Bahrain',
    'lb': 'Lebanon', 'om': 'Oman', 'iq': 'Iraq', 'ma': 'Morocco',
    'tn': 'Tunisia', 'dz': 'Algeria',
}


def parse_mourjan_listing(html, region, base_url='https://www.mourjan.com'):
    soup = BeautifulSoup(html, 'html.parser')
    jobs = []
    for card in soup.select('.ad'):
        anchor = card.select_one('a.link[href*="/vacancies/"]')
        content = card.select_one('.content')
        if not anchor or not content:
            continue
        description = clean_text(content.get_text(' ', strip=True))
        if not description:
            continue
        relevance_terms = (
            'python', 'django', 'flask', 'fastapi', 'odoo', 'backend', 'back-end',
            'software', 'website', 'web developer', 'application', 'api', '.net',
            'c#', 'java', 'php', 'react', 'node.js', 'مطور', 'مواقع', 'تطبيقات',
            'برمجيات', 'بايثون', 'أودو', 'اودو', 'واجهات',
        )
        if not any(term in description.lower() for term in relevance_terms):
            continue
        url = urljoin(base_url, anchor.get('href', '')).split('?')[0]
        path_parts = [part for part in urlparse(url).path.split('/') if part]
        city = path_parts[1].replace('-', ' ').title() if len(path_parts) > 4 else ''
        location = ', '.join(part for part in (city, MOURJAN_REGIONS.get(region, region.upper())) if part)
        time_node = card.select_one('.hint div:last-child')
        title = description.split('.')[0].strip()
        if len(title) > 90:
            title = title[:87].rsplit(' ', 1)[0] + '...'
        jobs.append({
            'title': title or 'Programming opportunity',
            'company': 'Direct advertiser',
            'location': location,
            'job_url': url,
            'description': description,
            'requirements': 'Contact the advertiser through Mourjan for complete requirements.',
            'job_type': 'Full-time',
            'posted_at': parse_relative_date(time_node.get_text(' ', strip=True) if time_node else ''),
            'source': 'Mourjan',
        })
    return jobs


def scrape_mourjan(limit=40, delay=0.2, output=None):
    session = build_session('https://www.mourjan.com/')
    jobs = []
    seen = set()
    successful_pages = 0
    for region in MOURJAN_REGIONS:
        url = f'https://www.mourjan.com/{region}/programming/vacancies/'
        try:
            parsed = parse_mourjan_listing(fetch_html(session, url), region)
            successful_pages += 1
        except (requests.RequestException, SourceUnavailable) as exc:
            if output:
                output(f'Mourjan {region.upper()} skipped: {exc}')
            continue
        for job in parsed:
            if job['job_url'] not in seen:
                seen.add(job['job_url'])
                jobs.append(job)
                if len(jobs) >= limit:
                    return jobs
        if delay:
            time.sleep(delay)
    if not successful_pages:
        raise SourceUnavailable('Mourjan did not return an accessible jobs page')
    return jobs


SCRAPERS = {
    'wuzzuf': ('Wuzzuf', scrape_wuzzuf),
    'bayt': ('Bayt', scrape_bayt),
    'mourjan': ('Mourjan', scrape_mourjan),
}
