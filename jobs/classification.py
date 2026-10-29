import re

from .models import Job


CATEGORY_RULES = (
    (Job.Category.ODOO_ERP, (
        'odoo', 'erp', 'sap', 'oracle ebs', 'oracle erp', 'dynamics 365',
        'microsoft dynamics', 'erpnext', 'netsuite', 'functional consultant',
    )),
    (Job.Category.DEVOPS, (
        'devops', 'site reliability', 'sre', 'platform engineer', 'ci/cd',
        'kubernetes', 'docker', 'terraform', 'ansible',
    )),
    (Job.Category.CLOUD, (
        'cloud engineer', 'cloud architect', 'aws', 'azure', 'gcp',
        'infrastructure engineer',
    )),
    (Job.Category.DATA_AI, (
        'data analyst', 'data engineer', 'data scientist', 'business intelligence',
        'power bi', 'tableau', 'machine learning', 'ml engineer', 'ai engineer',
        'artificial intelligence', 'database administrator', ' dba',
    )),
    (Job.Category.CYBERSECURITY, (
        'cybersecurity', 'cyber security', 'security engineer', 'soc analyst',
        'penetration tester', 'information security', 'application security',
    )),
    (Job.Category.QA, (
        'quality assurance', 'qa engineer', 'software tester', 'test automation',
        'automation tester', 'testing engineer',
    )),
    (Job.Category.IT_NETWORKS, (
        'it support', 'help desk', 'service desk', 'system administrator',
        'systems administrator', 'network engineer', 'noc engineer',
        'technical support', 'it specialist',
    )),
    (Job.Category.PRODUCT, (
        'product manager', 'product owner', 'project manager', 'scrum master',
        'program manager',
    )),
    (Job.Category.BUSINESS, (
        'business analyst', 'systems analyst', 'business systems',
    )),
    (Job.Category.UI_UX, (
        'ui designer', 'ux designer', 'ui/ux', 'product designer',
        'user experience',
    )),
    (Job.Category.TECH_SALES, (
        'presales', 'pre-sales', 'solutions consultant', 'sales engineer',
        'solution engineer',
    )),
    (Job.Category.SOFTWARE, (
        'developer', 'software engineer', 'backend', 'back-end', 'frontend',
        'front-end', 'full stack', 'full-stack', 'mobile engineer', 'android',
        'ios developer', 'python', 'django', 'fastapi', 'flask', 'java', '.net',
        'node.js', 'react', 'angular', 'php', 'laravel', 'programmer',
    )),
)

SKILL_TERMS = (
    'Python', 'Django', 'FastAPI', 'Flask', 'Odoo', 'SAP', 'Oracle ERP',
    'Dynamics 365', 'ERPNext', 'NetSuite', 'AWS', 'Azure', 'GCP', 'Docker',
    'Kubernetes', 'Terraform', 'Ansible', 'Power BI', 'Tableau', 'SQL',
    'Java', '.NET', 'Node.js', 'React', 'Angular', 'PHP', 'Laravel',
)


def classify_job(title, description='', requirements=''):
    title_text = (title or '').lower()
    text = ' '.join((title or '', description or '', requirements or '')).lower()
    category = Job.Category.OTHER
    for candidate, terms in CATEGORY_RULES:
        if any(term in title_text for term in terms):
            category = candidate
            break
    if category == Job.Category.OTHER:
        for candidate, terms in CATEGORY_RULES:
            if any(term in text for term in terms):
                category = candidate
                break
    skills = [
        skill for skill in SKILL_TERMS
        if re.search(rf'(?<!\w){re.escape(skill.lower())}(?!\w)', text)
    ]
    return category, skills
