import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from django.utils.text import slugify

from .job_sources import SourceUnavailable, build_session, fetch_html
from .wuzzuf import clean_text


def _split_company_meta(value):
    parts = [clean_text(part) for part in value.split('·') if clean_text(part)]
    return (parts[0] if parts else '', parts[1:] if len(parts) > 1 else [])


def parse_techny_startups(html, base_url='https://techny.dev'):
    soup = BeautifulSoup(html, 'html.parser')
    startups = []
    for row in soup.select('.sdtable .sdrow:not(.sdhead)'):
        name_link = row.select_one('.sdco a.nm[href^="/companies/"]')
        cells = row.select('[role="cell"]')
        if not name_link or len(cells) < 6:
            continue
        meta_node = row.select_one('.sdco small')
        country, sectors = _split_company_meta(meta_node.get_text(' ', strip=True) if meta_node else '')
        logo = row.select_one('.sdco img[src]')
        investor_links = row.select('.sdinv a')
        hiring_text = clean_text(cells[5].get_text(' ', strip=True))
        hiring_match = re.search(r'(\d+)', hiring_text)
        source_url = urljoin(base_url, name_link.get('href', ''))
        startups.append({
            'name': clean_text(name_link.get_text(' ', strip=True)),
            'slug': slugify(name_link.get('href', '').rstrip('/').split('/')[-1]) or slugify(name_link.get_text(' ', strip=True)),
            'country': country,
            'sectors': sectors,
            'stage': clean_text(cells[1].get_text(' ', strip=True)),
            'last_round': clean_text(cells[2].get_text(' ', strip=True)),
            'total_raised': clean_text(cells[3].get_text(' ', strip=True)),
            'investors': [clean_text(link.get_text(' ', strip=True)) for link in investor_links],
            'hiring_roles': int(hiring_match.group(1)) if hiring_match else 0,
            'logo_url': urljoin(base_url, logo.get('src', '')) if logo else '',
            'source_url': source_url,
            'source': 'Techny',
        })
    return startups


def scrape_techny_startups(limit=80, delay=0.2, output=None):
    session = build_session('https://techny.dev/startups')
    try:
        rows = parse_techny_startups(fetch_html(session, 'https://techny.dev/startups'))
    except (requests.RequestException, SourceUnavailable) as exc:
        raise SourceUnavailable(f'Techny public startup directory unavailable: {exc}') from exc
    if not rows:
        raise SourceUnavailable('Techny returned no public startup rows')
    if delay:
        time.sleep(min(delay, 0.5))
    return rows[:limit]
