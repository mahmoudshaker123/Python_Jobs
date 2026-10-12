import json
import re
import unicodedata
from html import unescape

from bs4 import BeautifulSoup


JOB_TYPE_MAP = {
    'FULL_TIME': 'Full-time',
    'PART_TIME': 'Part-time',
    'CONTRACTOR': 'Contract',
    'CONTRACT': 'Contract',
    'INTERN': 'Internship',
    'INTERNSHIP': 'Internship',
    'TEMPORARY': 'Contract',
    'FREELANCE': 'Freelance',
}


def clean_text(value, fallback=''):
    if value is None:
        return fallback
    text = unicodedata.normalize('NFKC', unescape(str(value)))
    text = text.replace('\ufffd', "'").replace('\xa0', ' ')
    text = '\n'.join(re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines())
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    return text.strip() or fallback


def _find_job_posting(soup):
    for script in soup.find_all('script', type='application/ld+json'):
        if not script.string:
            continue
        try:
            payload = json.loads(script.string)
        except (TypeError, json.JSONDecodeError):
            continue
        candidates = payload if isinstance(payload, list) else [payload]
        for item in candidates:
            if isinstance(item, dict) and item.get('@type') == 'JobPosting':
                return item
    return None


def _section_text(description_html, heading_name):
    fragment = BeautifulSoup(description_html or '', 'html.parser')
    heading = fragment.find(
        ['h1', 'h2', 'h3'],
        string=lambda value: value and heading_name in value.lower(),
    )
    if not heading:
        return ''

    parts = []
    for sibling in heading.next_siblings:
        if getattr(sibling, 'name', None) in {'h1', 'h2', 'h3'}:
            break
        if getattr(sibling, 'get_text', None):
            value = sibling.get_text('\n', strip=True)
        else:
            value = str(sibling).strip()
        if value:
            parts.append(value)
    return clean_text('\n'.join(parts))


def _location_from_posting(posting):
    if str(posting.get('jobLocationType', '')).upper() == 'TELECOMMUTE':
        return 'Remote'

    locations = posting.get('jobLocation') or []
    if isinstance(locations, dict):
        locations = [locations]

    values = []
    for location in locations:
        if not isinstance(location, dict):
            continue
        address = location.get('address') or {}
        if isinstance(address, str):
            candidate = clean_text(address)
        else:
            candidate = ', '.join(
                clean_text(address.get(key))
                for key in ('addressLocality', 'addressRegion', 'addressCountry')
                if clean_text(address.get(key))
            )
        if candidate and candidate not in values:
            values.append(candidate)

    location = ' / '.join(values)
    if not location or len(location) > 120 or '\n' in location:
        return 'Location not specified'
    return location


def _employment_type(posting):
    value = posting.get('employmentType') or ''
    if isinstance(value, list):
        value = value[0] if value else ''
    normalized = clean_text(value).upper().replace('-', '_').replace(' ', '_')
    return JOB_TYPE_MAP.get(normalized, 'Full-time')


def extract_job(html, url, fallback_title=''):
    soup = BeautifulSoup(html, 'html.parser')
    posting = _find_job_posting(soup)
    if not posting:
        return None

    description_html = posting.get('description') or ''
    description = _section_text(description_html, 'job description')
    requirements = _section_text(description_html, 'job requirements')
    if not description:
        description = clean_text(
            BeautifulSoup(description_html, 'html.parser').get_text('\n', strip=True),
            'Description available on the original job post.',
        )
    if not requirements:
        requirements = 'See the original job post for full requirements.'

    organization = posting.get('hiringOrganization') or {}
    company = clean_text(
        organization.get('name') if isinstance(organization, dict) else organization,
        'Company not disclosed',
    )
    salary = posting.get('baseSalary') or {}
    salary_text = clean_text(salary.get('value') if isinstance(salary, dict) else salary, 'Not specified')

    return {
        'title': clean_text(posting.get('title'), clean_text(fallback_title, 'Untitled role')),
        'company': company,
        'location': _location_from_posting(posting),
        'job_url': url,
        'description': description,
        'requirements': requirements,
        'experience': 'See original job post',
        'salary': salary_text,
        'job_type': _employment_type(posting),
        'date_posted': clean_text(posting.get('datePosted')),
    }
