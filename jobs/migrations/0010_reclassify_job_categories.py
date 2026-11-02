import re

from django.db import migrations


RULES = (
    ('odoo_erp', ('odoo', 'erp', 'sap', 'oracle ebs', 'oracle erp', 'dynamics 365',
                  'microsoft dynamics', 'erpnext', 'netsuite', 'functional consultant')),
    ('devops', ('devops', 'site reliability', 'sre', 'platform engineer', 'ci/cd',
                'kubernetes', 'docker', 'terraform', 'ansible')),
    ('cloud', ('cloud engineer', 'cloud architect', 'aws', 'azure', 'gcp',
               'infrastructure engineer')),
    ('data_ai', ('data analyst', 'data engineer', 'data scientist', 'business intelligence',
                 'power bi', 'tableau', 'machine learning', 'ml engineer', 'ai engineer',
                 'artificial intelligence', 'database administrator', 'dba')),
    ('cybersecurity', ('cybersecurity', 'cyber security', 'security engineer', 'soc analyst',
                       'penetration tester', 'information security', 'application security')),
    ('qa', ('quality assurance', 'qa engineer', 'software tester', 'test automation',
            'automation tester', 'testing engineer')),
    ('it_networks', ('it support', 'help desk', 'service desk', 'system administrator',
                     'systems administrator', 'network engineer', 'noc engineer',
                     'technical support', 'it specialist')),
    ('product', ('product manager', 'product owner', 'project manager', 'scrum master',
                 'program manager')),
    ('business', ('business analyst', 'systems analyst', 'business systems')),
    ('ui_ux', ('ui designer', 'ux designer', 'ui/ux', 'product designer', 'user experience')),
    ('tech_sales', ('presales', 'pre-sales', 'solutions consultant', 'sales engineer',
                    'solution engineer')),
    ('software', ('developer', 'software engineer', 'backend', 'back-end', 'frontend',
                  'front-end', 'full stack', 'full-stack', 'mobile engineer', 'android',
                  'ios developer', 'python', 'django', 'fastapi', 'flask', 'java', '.net',
                  'node.js', 'react', 'angular', 'php', 'laravel', 'programmer')),
)


def contains_term(text, term):
    return bool(re.search(rf'(?<!\w){re.escape(term)}(?!\w)', text))


def classify(text):
    for category, terms in RULES:
        if any(contains_term(text, term) for term in terms):
            return category
    return 'other'


def reclassify_jobs(apps, schema_editor):
    Job = apps.get_model('jobs', 'Job')
    for job in Job.objects.all().iterator():
        title = (job.title or '').lower()
        category = classify(title)
        if category == 'other':
            combined = ' '.join((job.title or '', job.description or '', job.requirement or '')).lower()
            category = classify(combined)
        if job.category != category:
            Job.objects.filter(pk=job.pk).update(category=category)


class Migration(migrations.Migration):
    dependencies = [('jobs', '0009_companyreview')]
    operations = [migrations.RunPython(reclassify_jobs, migrations.RunPython.noop)]
