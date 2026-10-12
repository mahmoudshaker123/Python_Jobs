import json

from django.test import SimpleTestCase

from jobs.wuzzuf import extract_job


class WuzzufParserTest(SimpleTestCase):
    def page(self, **overrides):
        posting = {
            '@context': 'https://schema.org/',
            '@type': 'JobPosting',
            'title': 'Senior Python Engineer',
            'description': (
                '<section><h1>Job Description</h1><p>Build reliable APIs.</p></section>'
                '<section><h1>Job Requirements</h1><ul><li>Strong Python</li></ul></section>'
            ),
            'employmentType': 'FULL_TIME',
            'datePosted': 'Tue, 08 Apr 2025 14:36:51 GMT',
            'hiringOrganization': {'name': 'Acme Tech'},
            'jobLocation': {
                'address': {
                    'addressLocality': 'New Cairo',
                    'addressRegion': 'Cairo',
                    'addressCountry': 'EG',
                }
            },
        }
        posting.update(overrides)
        return f'<script type="application/ld+json">{json.dumps(posting)}</script>'

    def test_extracts_structured_fields_without_description_leaking_into_location(self):
        job = extract_job(self.page(), 'https://wuzzuf.net/jobs/p/example')
        self.assertEqual(job['company'], 'Acme Tech')
        self.assertEqual(job['location'], 'New Cairo, Cairo, EG')
        self.assertEqual(job['job_type'], 'Full-time')
        self.assertEqual(job['description'], 'Build reliable APIs.')
        self.assertEqual(job['requirements'], 'Strong Python')

    def test_remote_and_missing_values_have_safe_fallbacks(self):
        job = extract_job(
            self.page(
                hiringOrganization={},
                jobLocation={},
                jobLocationType='TELECOMMUTE',
                employmentType='CONTRACTOR',
            ),
            'https://wuzzuf.net/jobs/p/remote',
        )
        self.assertEqual(job['company'], 'Company not disclosed')
        self.assertEqual(job['location'], 'Remote')
        self.assertEqual(job['job_type'], 'Contract')

    def test_page_without_jobposting_is_skipped(self):
        self.assertIsNone(extract_job('<html></html>', 'https://wuzzuf.net/jobs/p/missing'))
