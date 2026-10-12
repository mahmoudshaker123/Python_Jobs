from django.test import SimpleTestCase

from jobs.job_sources import parse_bayt_listing, parse_mourjan_listing


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
