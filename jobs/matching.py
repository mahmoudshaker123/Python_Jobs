import re
from io import BytesIO

from pypdf import PdfReader

from .classification import CATEGORY_RULES, SKILL_TERMS


EXTRA_TERMS = (
    'DevOps', 'SRE', 'Linux', 'Git', 'CI/CD', 'REST', 'API', 'PostgreSQL',
    'MySQL', 'MongoDB', 'Redis', 'Celery', 'JavaScript', 'TypeScript', 'HTML',
    'CSS', 'Flutter', 'React Native', 'Cybersecurity', 'Networking', 'Figma',
    'Scrum', 'Agile', 'Salesforce', 'ServiceNow', 'ABAP', 'ERP', 'CRM',
)


def extract_cv_text(upload):
    payload = upload.read()
    suffix = upload.name.lower().rsplit('.', 1)[-1]
    if suffix == 'txt':
        return payload.decode('utf-8', errors='ignore')
    reader = PdfReader(BytesIO(payload), strict=False)
    return '\n'.join((page.extract_text() or '') for page in reader.pages[:12])


def _terms_in_text(text):
    lowered = text.lower()
    terms = []
    for term in (*SKILL_TERMS, *EXTRA_TERMS):
        if re.search(rf'(?<!\w){re.escape(term.lower())}(?!\w)', lowered):
            terms.append(term)
    return list(dict.fromkeys(terms))


def _category_hints(text):
    lowered = text.lower()
    return {
        category for category, terms in CATEGORY_RULES
        if any(term in lowered for term in terms)
    }


def rank_jobs_for_cv(cv_text, jobs, limit=20):
    cv_terms = _terms_in_text(cv_text)
    cv_categories = _category_hints(cv_text)
    cv_words = set(re.findall(r'[a-zA-Z][a-zA-Z0-9+#.\-/]{2,}', cv_text.lower()))
    ranked = []

    for job in jobs:
        title = (job.title or '').lower()
        body = ' '.join((job.description or '', job.requirement or '')).lower()
        job_terms = set(job.skills or []) | set(_terms_in_text(f'{job.title} {body}'))
        matched_terms = [term for term in cv_terms if term in job_terms]
        title_overlap = sum(1 for word in cv_words if word in title)
        body_overlap = sum(1 for word in cv_words if len(word) > 4 and word in body)
        score = len(matched_terms) * 12 + min(title_overlap, 6) * 7 + min(body_overlap, 8) * 2
        if job.category in cv_categories:
            score += 18
        if score <= 0:
            continue
        confidence = min(98, 28 + score)
        ranked.append({
            'job': job,
            'score': confidence,
            'matched_skills': matched_terms[:8],
        })

    ranked.sort(key=lambda item: (item['score'], item['job'].posted_at), reverse=True)
    return ranked[:limit]
