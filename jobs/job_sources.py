import re
import time
from datetime import datetime, time as datetime_time, timedelta
from urllib.parse import urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from django.utils import timezone
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .wuzzuf import clean_text, extract_job
from .classification import classify_job


class SourceUnavailable(RuntimeError):
    """Raised when a source blocks or cannot serve a usable jobs page."""


def rotating_batch(values, size):
    """Rotate broad searches hourly so serverless runs stay within their time limit."""
    values = tuple(values)
    if len(values) <= size:
        return values
    batch_count = (len(values) + size - 1) // size
    batch_index = int(timezone.now().timestamp() // 3600) % batch_count
    start = batch_index * size
    batch = values[start:start + size]
    if len(batch) < size:
        batch += values[:size - len(batch)]
    return batch


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
    all_searches = (
        ('Odoo Developer', 'https://wuzzuf.net/search/jobs/?q=odoo%20developer&a=hpb'),
        ('Odoo Implementer', 'https://wuzzuf.net/search/jobs/?q=odoo%20implementer&a=hpb'),
        ('ERP Consultant', 'https://wuzzuf.net/search/jobs/?q=erp%20consultant&a=hpb'),
        ('SAP Consultant', 'https://wuzzuf.net/search/jobs/?q=sap%20consultant&a=hpb'),
        ('Dynamics 365', 'https://wuzzuf.net/search/jobs/?q=dynamics%20365&a=hpb'),
        ('Python Developer', 'https://wuzzuf.net/search/jobs/?q=python%20developer&a=hpb'),
        ('Python Backend', 'https://wuzzuf.net/search/jobs/?q=python%20django%20backend&a=hpb'),
        ('Software Engineer', 'https://wuzzuf.net/search/jobs/?q=software%20engineer&a=hpb'),
        ('Frontend Developer', 'https://wuzzuf.net/search/jobs/?q=frontend%20developer&a=hpb'),
        ('Full Stack Developer', 'https://wuzzuf.net/search/jobs/?q=full%20stack%20developer&a=hpb'),
        ('DevOps Engineer', 'https://wuzzuf.net/search/jobs/?q=devops%20engineer&a=hpb'),
        ('Cloud Engineer', 'https://wuzzuf.net/search/jobs/?q=cloud%20engineer&a=hpb'),
        ('System Administrator', 'https://wuzzuf.net/search/jobs/?q=system%20administrator&a=hpb'),
        ('Network Engineer', 'https://wuzzuf.net/search/jobs/?q=network%20engineer&a=hpb'),
        ('IT Support', 'https://wuzzuf.net/search/jobs/?q=it%20support&a=hpb'),
        ('Data Analyst', 'https://wuzzuf.net/search/jobs/?q=data%20analyst&a=hpb'),
        ('Data Engineer', 'https://wuzzuf.net/search/jobs/?q=data%20engineer&a=hpb'),
        ('Power BI', 'https://wuzzuf.net/search/jobs/?q=power%20bi&a=hpb'),
        ('Machine Learning', 'https://wuzzuf.net/search/jobs/?q=machine%20learning%20engineer&a=hpb'),
        ('Cyber Security', 'https://wuzzuf.net/search/jobs/?q=cyber%20security&a=hpb'),
        ('QA Engineer', 'https://wuzzuf.net/search/jobs/?q=qa%20engineer&a=hpb'),
        ('Business Analyst', 'https://wuzzuf.net/search/jobs/?q=business%20analyst&a=hpb'),
    )
    searches = rotating_batch(all_searches, 8)
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
    searches = rotating_batch((
        'https://www.bayt.com/en/international/jobs/odoo-developer-jobs/',
        'https://www.bayt.com/en/international/jobs/odoo-consultant-jobs/',
        'https://www.bayt.com/en/international/jobs/erp-consultant-jobs/',
        'https://www.bayt.com/en/international/jobs/sap-consultant-jobs/',
        'https://www.bayt.com/en/international/jobs/python-developer-jobs/',
        'https://www.bayt.com/en/international/jobs/python-django-jobs/',
        'https://www.bayt.com/en/international/jobs/software-engineer-jobs/',
        'https://www.bayt.com/en/international/jobs/full-stack-developer-jobs/',
        'https://www.bayt.com/en/international/jobs/devops-engineer-jobs/',
        'https://www.bayt.com/en/international/jobs/cloud-engineer-jobs/',
        'https://www.bayt.com/en/international/jobs/it-support-jobs/',
        'https://www.bayt.com/en/international/jobs/network-engineer-jobs/',
        'https://www.bayt.com/en/international/jobs/data-analyst-jobs/',
        'https://www.bayt.com/en/international/jobs/data-engineer-jobs/',
        'https://www.bayt.com/en/international/jobs/power-bi-jobs/',
        'https://www.bayt.com/en/international/jobs/cyber-security-jobs/',
        'https://www.bayt.com/en/international/jobs/qa-engineer-jobs/',
    ), 8)
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


LINKEDIN_SEARCHES = (
    'Odoo Developer',
    'Odoo Functional Consultant',
    'Odoo Implementer',
    'Python Developer',
    'Python Backend Developer',
    'Django Developer',
    'ERP Consultant',
    'SAP Consultant',
    'Microsoft Dynamics 365 Consultant',
    'Software Engineer',
    'Backend Developer',
    'Frontend Developer',
    'Full Stack Developer',
    'Mobile Developer',
    'DevOps Engineer',
    'Site Reliability Engineer',
    'Cloud Engineer',
    'AWS Engineer',
    'Azure Engineer',
    'Data Analyst',
    'Data Engineer',
    'Power BI Developer',
    'Data Scientist',
    'Machine Learning Engineer',
    'IT Support Engineer',
    'System Administrator',
    'Network Engineer',
    'Cyber Security Engineer',
    'QA Automation Engineer',
    'Business Analyst',
)

LINKEDIN_RELEVANCE_TERMS = (
    'odoo', 'erp', 'python', 'django', 'fastapi', 'flask', 'developer',
    'engineer', 'devops', 'cloud', 'data', 'power bi', 'administrator',
    'network', 'security', 'quality assurance', 'qa ', 'business analyst',
    'sap', 'dynamics 365',
)

LINKEDIN_SEARCH_SCOPES = (
    ('Middle East and North Africa', False),
    ('Egypt', False),
    ('Worldwide', True),
)

ARAB_LOCATION_TERMS = (
    'egypt', 'united arab emirates', 'uae', 'saudi arabia', 'ksa',
    'qatar', 'kuwait', 'bahrain', 'oman', 'jordan', 'lebanon', 'iraq',
    'morocco', 'tunisia', 'algeria', 'libya', 'palestine', 'palestinian',
    'yemen', 'sudan', 'syria', 'mauritania', 'somalia', 'djibouti', 'comoros',
)

REMOTE_LOCATION_TERMS = (
    'remote', 'remotely', 'work from home', 'work-from-home', 'anywhere',
    'worldwide',
)


def _contains_location_term(location, term):
    return bool(re.search(rf'(?<!\w){re.escape(term)}(?!\w)', location, re.I))


def is_allowed_linkedin_location(location):
    location = clean_text(location)
    return any(
        _contains_location_term(location, term)
        for term in ARAB_LOCATION_TERMS + REMOTE_LOCATION_TERMS
    )


def _linkedin_posted_at(value):
    value = clean_text(value)
    if value:
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(
                    datetime.combine(parsed.date(), datetime_time.min),
                    timezone.get_current_timezone(),
                )
            return parsed
        except ValueError:
            pass
    return timezone.now()


def parse_linkedin_listing(html):
    soup = BeautifulSoup(html, 'html.parser')
    jobs = []
    seen = set()
    for card in soup.select('[data-entity-urn*="jobPosting:"]'):
        urn = card.get('data-entity-urn', '')
        match = re.search(r'jobPosting:(\d+)', urn)
        title_node = card.select_one('.base-search-card__title')
        if not match or not title_node:
            continue
        job_id = match.group(1)
        if job_id in seen:
            continue
        seen.add(job_id)
        company_node = card.select_one('.base-search-card__subtitle')
        location_node = card.select_one('.job-search-card__location')
        date_node = card.select_one('time[datetime]')
        jobs.append({
            'linkedin_id': job_id,
            'title': clean_text(title_node.get_text(' ', strip=True)),
            'company': clean_text(company_node.get_text(' ', strip=True)) if company_node else 'Company not disclosed',
            'location': clean_text(location_node.get_text(' ', strip=True)) if location_node else 'Location not specified',
            'job_url': f'https://www.linkedin.com/jobs/view/{job_id}/',
            'description': 'Description available on the original LinkedIn job post.',
            'requirements': 'See the original LinkedIn job post for full requirements.',
            'job_type': 'Full-time',
            'posted_at': _linkedin_posted_at(date_node.get('datetime', '') if date_node else ''),
            'source': 'LinkedIn',
        })
    return jobs


def parse_linkedin_detail(html):
    soup = BeautifulSoup(html, 'html.parser')
    description_node = soup.select_one('.show-more-less-html__markup')
    description = clean_text(description_node.get_text(' ', strip=True)) if description_node else ''
    criteria = {}
    for item in soup.select('.description__job-criteria-item'):
        label = item.select_one('.description__job-criteria-subheader')
        value = item.select_one('.description__job-criteria-text')
        if label and value:
            criteria[clean_text(label.get_text(' ', strip=True)).lower()] = clean_text(
                value.get_text(' ', strip=True)
            )
    employment_type = criteria.get('employment type', '')
    job_type = 'Full-time'
    for candidate in ('Part-time', 'Contract', 'Internship', 'Freelance'):
        if candidate.lower() in employment_type.lower():
            job_type = candidate
            break
    requirements = '; '.join(
        f'{label.title()}: {value}'
        for label, value in criteria.items()
        if label in {'seniority level', 'employment type', 'job function', 'industries'}
    )
    return {
        'description': description,
        'requirements': requirements,
        'job_type': job_type,
    }


def scrape_linkedin(limit=40, delay=0.2, output=None):
    session = build_session('https://www.linkedin.com/jobs/search/')
    jobs = []
    seen = set()
    successful_pages = 0
    searches = rotating_batch(LINKEDIN_SEARCHES, 10)
    quota = max(1, limit // len(searches))
    detail_budget = min(limit, 12)

    for index, keywords in enumerate(searches):
        query_limit = quota if index < len(searches) - 1 else limit - len(jobs)
        keyword_added = 0
        for scope_index, (location, remote_only) in enumerate(LINKEDIN_SEARCH_SCOPES):
            if keyword_added >= query_limit or len(jobs) >= limit:
                break
            scopes_left = len(LINKEDIN_SEARCH_SCOPES) - scope_index
            scope_limit = max(1, (query_limit - keyword_added + scopes_left - 1) // scopes_left)
            params = {
                'keywords': keywords,
                'location': location,
                'f_TPR': 'r2592000',
                'start': 0,
            }
            if remote_only:
                params['f_WT'] = '2'
            search_url = (
                'https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?'
                f'{urlencode(params)}'
            )
            try:
                listing_jobs = parse_linkedin_listing(fetch_html(session, search_url))
                successful_pages += 1
            except (requests.RequestException, SourceUnavailable) as exc:
                if output:
                    output(f'LinkedIn {keywords} / {location} page skipped: {exc}')
                continue

            scope_added = 0
            for job in listing_jobs:
                if (
                    job['linkedin_id'] in seen
                    or scope_added >= scope_limit
                    or keyword_added >= query_limit
                    or len(jobs) >= limit
                ):
                    continue
                if not any(term in job['title'].lower() for term in LINKEDIN_RELEVANCE_TERMS):
                    continue
                if remote_only:
                    if not any(
                        _contains_location_term(job['location'], term)
                        for term in REMOTE_LOCATION_TERMS
                    ):
                        job['location'] = f"Remote — {job['location']}"
                elif not is_allowed_linkedin_location(job['location']):
                    continue
                seen.add(job['linkedin_id'])
                if detail_budget:
                    detail_url = (
                        'https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/'
                        f"{job['linkedin_id']}"
                    )
                    try:
                        details = parse_linkedin_detail(fetch_html(session, detail_url))
                        if details['description']:
                            job['description'] = details['description']
                        if details['requirements']:
                            job['requirements'] = details['requirements']
                        job['job_type'] = details['job_type']
                    except (requests.RequestException, SourceUnavailable) as exc:
                        if output:
                            output(f"LinkedIn job {job['linkedin_id']} details skipped: {exc}")
                    detail_budget -= 1
                job.pop('linkedin_id', None)
                jobs.append(job)
                scope_added += 1
                keyword_added += 1
                if delay and detail_budget:
                    time.sleep(max(delay, 0.4))
            if delay:
                time.sleep(max(delay, 0.25))

    if not successful_pages:
        raise SourceUnavailable('LinkedIn did not return an accessible public jobs page')
    return jobs[:limit]


def scrape_arbeitnow(limit=40, delay=0.2, output=None):
    """Collect relevant worldwide-remote technology roles from Arbeitnow's API."""
    session = build_session('https://www.arbeitnow.com/')
    jobs = []
    seen = set()
    page = 1
    while len(jobs) < limit and page <= 8:
        try:
            response = session.get(
                'https://www.arbeitnow.com/api/job-board-api',
                params={'page': page},
                timeout=25,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            if not jobs:
                raise SourceUnavailable(f'Arbeitnow API unavailable: {exc}') from exc
            break
        rows = payload.get('data') or []
        if not rows:
            break
        for row in rows:
            if not row.get('remote'):
                continue
            title = clean_text(row.get('title'))
            description = clean_text(BeautifulSoup(row.get('description') or '', 'html.parser').get_text(' '))
            category, skills = classify_job(title)
            if category == 'other':
                continue
            _, skills = classify_job(title, description)
            url = row.get('url')
            if not url or url in seen:
                continue
            seen.add(url)
            created_at = row.get('created_at')
            try:
                posted_at = datetime.fromtimestamp(int(created_at), tz=timezone.get_current_timezone())
            except (TypeError, ValueError, OSError):
                posted_at = timezone.now()
            jobs.append({
                'title': title,
                'company': clean_text(row.get('company_name')) or 'Company not disclosed',
                'location': f"Remote - {clean_text(row.get('location')) or 'Worldwide'}",
                'job_url': url,
                'description': description or 'See the original Arbeitnow job post.',
                'requirements': ', '.join(row.get('tags') or []) or 'See the original job post.',
                'job_type': 'Full-time',
                'posted_at': posted_at,
                'source': 'Arbeitnow',
                'category': category,
                'skills': skills,
            })
            if len(jobs) >= limit:
                break
        page += 1
        if delay:
            time.sleep(delay)
    if not jobs:
        raise SourceUnavailable('Arbeitnow returned no matching remote technology jobs')
    return jobs


SCRAPERS = {
    'wuzzuf': ('Wuzzuf', scrape_wuzzuf),
    'bayt': ('Bayt', scrape_bayt),
    'mourjan': ('Mourjan', scrape_mourjan),
    'linkedin': ('LinkedIn', scrape_linkedin),
    'arbeitnow': ('Arbeitnow', scrape_arbeitnow),
}
