import re
from collections import Counter
from math import log, sqrt
from io import BytesIO

from pypdf import PdfReader

from .classification import CATEGORY_RULES, SKILL_TERMS


EXTRA_TERMS = (
    'DevOps', 'SRE', 'Linux', 'Git', 'CI/CD', 'REST', 'API', 'PostgreSQL',
    'MySQL', 'MongoDB', 'Redis', 'Celery', 'JavaScript', 'TypeScript', 'HTML',
    'CSS', 'Flutter', 'React Native', 'Cybersecurity', 'Networking', 'Figma',
    'Scrum', 'Agile', 'Salesforce', 'ServiceNow', 'ABAP', 'ERP', 'CRM',
    'GitHub Actions', 'GitLab CI', 'Jenkins', 'Nginx', 'Apache', 'Pandas',
    'NumPy', 'Spark', 'Airflow', 'dbt', 'Snowflake', 'BigQuery', 'Kafka',
    'RabbitMQ', 'GraphQL', 'Microservices', 'Selenium', 'Playwright', 'Pytest',
    'Bash', 'PowerShell', 'Kotlin', 'Swift', 'C++', 'C#',
)

ARABIC_CATEGORY_HINTS = {
    'odoo_erp': ('أودو', 'اودو', 'تخطيط موارد', 'نظم erp', 'استشاري وظيفي'),
    'devops': ('ديف أوبس', 'ديفوبس', 'موثوقية المواقع', 'خطوط النشر'),
    'cloud': ('حوسبة سحابية', 'مهندس سحابة', 'بنية تحتية'),
    'data_ai': ('تحليل البيانات', 'مهندس بيانات', 'ذكاء اصطناعي', 'تعلم آلي'),
    'cybersecurity': ('أمن سيبراني', 'امن سيبراني', 'أمن المعلومات'),
    'qa': ('اختبار البرمجيات', 'ضمان الجودة', 'مهندس اختبار'),
    'it_networks': ('دعم فني', 'شبكات', 'مسؤول نظم'),
    'product': ('مدير منتج', 'مدير مشروع', 'مالك المنتج'),
    'business': ('محلل أعمال', 'محلل نظم'),
    'ui_ux': ('تجربة المستخدم', 'واجهة المستخدم', 'مصمم منتجات'),
    'tech_sales': ('مبيعات تقنية', 'ما قبل البيع'),
    'software': ('مطور', 'مبرمج', 'مهندس برمجيات', 'تطوير البرمجيات'),
}


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
    categories = {
        category for category, terms in CATEGORY_RULES
        if any(term in lowered for term in terms)
    }
    categories.update({
        category for category, terms in ARABIC_CATEGORY_HINTS.items()
        if any(term in lowered for term in terms)
    })
    return categories


def rank_jobs_for_cv(cv_text, jobs, limit=20):
    cv_terms = _terms_in_text(cv_text)
    cv_categories = _category_hints(cv_text)
    cv_tokens = _tokenize(cv_text)
    cv_years = _years_experience(cv_text)
    jobs = list(jobs)
    documents = []
    document_frequency = Counter()
    for job in jobs:
        title = job.title or ''
        requirements = job.requirement or ''
        description = job.description or ''
        skills = job.skills or []
        if isinstance(skills, str):
            skills = [part.strip() for part in re.split(r'[,|;]', skills) if part.strip()]
        weighted_text = ' '.join((title, title, title, requirements, requirements,
                                  description, ' '.join(skills), ' '.join(skills)))
        tokens = _tokenize(weighted_text)
        documents.append((tokens, title, requirements, description, skills))
        document_frequency.update(set(tokens))

    corpus_size = max(len(documents), 1)
    cv_vector = _tfidf_vector(cv_tokens, document_frequency, corpus_size)
    ranked = []

    for job, (tokens, title_text, requirement_text, description_text, skills) in zip(jobs, documents):
        job_terms = list(dict.fromkeys([
            *skills,
            *_terms_in_text(f'{title_text} {requirement_text} {description_text}'),
        ]))
        cv_term_keys = {item.casefold() for item in cv_terms}
        job_term_map = {item.casefold(): item for item in job_terms}
        matched_terms = [job_term_map[item.casefold()] for item in cv_terms if item.casefold() in job_term_map]
        missing_terms = [item for item in job_terms if item.casefold() not in cv_term_keys]
        job_vector = _tfidf_vector(tokens, document_frequency, corpus_size)
        semantic_overlap = _cosine(cv_vector, job_vector)
        cv_token_set = set(cv_tokens)
        requirement_tokens = set(_tokenize(requirement_text))
        requirement_overlap = len(requirement_tokens & cv_token_set)
        cv_requirement_coverage = (
            min(requirement_overlap / min(len(requirement_tokens), 12), 1)
            if requirement_tokens else 0
        )
        title_tokens = set(_role_tokens(title_text))
        title_relevance = (
            len(title_tokens & cv_token_set) / len(title_tokens)
            if title_tokens else 0
        )
        category_relevance = 1 if job.category in cv_categories else 0
        skill_coverage = len(matched_terms) / max(len(job_terms), 1)
        seniority_fit = _seniority_fit(cv_years, job.seniority, title_text)

        # Skill coverage and role requirements dominate; lexical similarity is
        # deliberately only one signal so generic CV wording cannot win alone.
        score = round(100 * (
            0.45 * skill_coverage
            + 0.20 * title_relevance
            + 0.15 * cv_requirement_coverage
            + 0.10 * semantic_overlap
            + 0.05 * category_relevance
            + 0.05 * seniority_fit
        ))
        if (not matched_terms and title_relevance < 0.2 and semantic_overlap < 0.08) or score < 12:
            continue
        reasons = []
        if matched_terms:
            reasons.append('skills')
        if title_relevance >= 0.4:
            reasons.append('title')
        if category_relevance:
            reasons.append('field')
        if cv_years is not None and seniority_fit >= 0.8:
            reasons.append('experience')
        ranked.append({
            'job': job,
            'score': min(99, score),
            'matched_skills': matched_terms[:8],
            'missing_skills': missing_terms[:6],
            'reasons': reasons,
        })

    ranked.sort(key=lambda item: (item['score'], item['job'].posted_at), reverse=True)
    return ranked[:limit]


_STOP_WORDS = {
    'and', 'the', 'for', 'with', 'from', 'this', 'that', 'have', 'has', 'are',
    'was', 'were', 'will', 'you', 'your', 'our', 'their', 'they', 'who', 'what',
    'when', 'where', 'which', 'while', 'into', 'about', 'over', 'under', 'more',
    'years', 'year', 'experience', 'work', 'working', 'role', 'team', 'job',
    'skills', 'ability', 'strong', 'good', 'using', 'use', 'including', 'required',
    'preferred', 'responsibilities', 'requirements', 'candidate', 'company',
    'في', 'من', 'إلى', 'الى', 'على', 'عن', 'مع', 'هذا', 'هذه', 'التي', 'الذي',
    'خبرة', 'سنوات', 'سنة', 'عمل', 'فريق', 'مهارات', 'مطلوب', 'القدرة',
}

_TITLE_NOISE = {
    'senior', 'sr', 'junior', 'jr', 'lead', 'principal', 'staff', 'head',
    'manager', 'specialist', 'engineer', 'developer', 'consultant', 'analyst',
    'intern', 'internship', 'remote', 'مهندس', 'مطور', 'كبير', 'مبتدئ',
}


def _tokenize(text):
    tokens = re.findall(r'[a-z\u0600-\u06ff][a-z0-9\u0600-\u06ff+#./-]{1,}', (text or '').lower())
    return [token for token in tokens if token not in _STOP_WORDS]


def _role_tokens(text):
    tokens = [token for token in _tokenize(text) if token not in _TITLE_NOISE]
    return tokens or _tokenize(text)


def _tfidf_vector(tokens, document_frequency, corpus_size):
    counts = Counter(tokens)
    length = max(len(tokens), 1)
    return {
        token: (count / length) * (1 + log((corpus_size + 1) / (document_frequency[token] + 1)))
        for token, count in counts.items()
    }


def _cosine(left, right):
    if not left or not right:
        return 0
    dot = sum(value * right.get(token, 0) for token, value in left.items())
    denominator = sqrt(sum(value * value for value in left.values())) * sqrt(
        sum(value * value for value in right.values())
    )
    return dot / denominator if denominator else 0


def _years_experience(text):
    values = re.findall(r'\b(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b', text or '', re.I)
    word_numbers = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
    }
    for word, number in word_numbers.items():
        if re.search(rf'\b{word}\s*\+?\s*(?:years?|yrs?)\b', text or '', re.I):
            values.append(str(number))
    return max((int(value) for value in values), default=None)


def _seniority_fit(cv_years, seniority, title):
    label = f'{seniority or ""} {title or ""}'.lower()
    if any(word in label for word in ('junior', 'entry level', 'graduate', 'intern')):
        return 1 if cv_years is None or cv_years <= 3 else 0.6
    if any(word in label for word in ('senior', 'lead', 'principal', 'staff')):
        if cv_years is None:
            return 0.5
        return min(cv_years / 5, 1)
    return 0.75 if cv_years is not None else 0.5
