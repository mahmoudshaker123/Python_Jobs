from django.test import SimpleTestCase

from jobs.job_sources import (
    parse_bayt_listing,
    is_allowed_linkedin_location,
    parse_linkedin_detail,
    parse_linkedin_listing,
    parse_mourjan_listing,
)


class BaytParserTest(SimpleTestCase):
    def test_extracts_listing_card_without_leaking_summary_into_location(self):
        html = '''
        <ul><li class="job-card">
          <h2><a href="/en/saudi-arabia/jobs/odoo-developer-1234567/">Odoo Developer</a></h2>
          <a href="/en/company/acme/">Acme ERP</a>
          <p>Summary: Build and customize Odoo modules with Python.</p>
          <span>Riyadh, Saudi Arabia</span><span>2 days ago</span><span>Full time</span>
        </li></ul>
        '''
        jobs = parse_bayt_listing(html)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]['title'], 'Odoo Developer')
        self.assertEqual(jobs[0]['company'], 'Acme ERP')
        self.assertEqual(jobs[0]['location'], 'Riyadh, Saudi Arabia')
        self.assertIn('Odoo modules', jobs[0]['description'])


class MourjanParserTest(SimpleTestCase):
    def test_extracts_programming_classified(self):
        html = '''
        <div class="ad"><a class="link" href="/ae/dubai/programming/vacancies/123/">
          <div class="hint"><div>شركة</div><div>منذ 3 ساعات</div></div>
          <div class="content">مطلوب مطور Odoo وPython للعمل بدوام كامل في دبي.</div>
        </a></div>
        '''
        jobs = parse_mourjan_listing(html, 'ae')
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]['location'], 'Dubai, United Arab Emirates')
        self.assertIn('Odoo', jobs[0]['title'])
        self.assertEqual(jobs[0]['source'], 'Mourjan')


class LinkedInParserTest(SimpleTestCase):
    def test_allows_arab_locations_and_worldwide_remote_only(self):
        self.assertTrue(is_allowed_linkedin_location('Cairo, Egypt'))
        self.assertTrue(is_allowed_linkedin_location('Riyadh, Saudi Arabia'))
        self.assertTrue(is_allowed_linkedin_location('Remote — Berlin, Germany'))
        self.assertFalse(is_allowed_linkedin_location('Berlin, Germany'))
        self.assertFalse(is_allowed_linkedin_location('Bengaluru, India'))

    def test_extracts_public_job_card_and_canonical_url(self):
        html = '''
        <li><div class="base-search-card" data-entity-urn="urn:li:jobPosting:123456">
          <h3 class="base-search-card__title">Odoo Functional Consultant</h3>
          <h4 class="base-search-card__subtitle"><a>ERP Experts</a></h4>
          <span class="job-search-card__location">Remote</span>
          <time class="job-search-card__listdate" datetime="2026-10-20">1 day ago</time>
        </div></li>
        '''
        jobs = parse_linkedin_listing(html)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]['title'], 'Odoo Functional Consultant')
        self.assertEqual(jobs[0]['company'], 'ERP Experts')
        self.assertEqual(jobs[0]['job_url'], 'https://www.linkedin.com/jobs/view/123456/')
        self.assertEqual(jobs[0]['source'], 'LinkedIn')

    def test_extracts_description_and_employment_type(self):
        html = '''
        <div class="show-more-less-html__markup">Implement Odoo modules and integrations.</div>
        <li class="description__job-criteria-item">
          <h3 class="description__job-criteria-subheader">Employment type</h3>
          <span class="description__job-criteria-text">Contract</span>
        </li>
        <li class="description__job-criteria-item">
          <h3 class="description__job-criteria-subheader">Seniority level</h3>
          <span class="description__job-criteria-text">Mid-Senior level</span>
        </li>
        '''
        details = parse_linkedin_detail(html)
        self.assertIn('Odoo modules', details['description'])
        self.assertEqual(details['job_type'], 'Contract')
        self.assertIn('Mid-Senior level', details['requirements'])
