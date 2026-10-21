from django.test import TestCase
from django.urls import reverse

from jobs.models import Company, EmailSubscription, Job


class JobViewsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        company = Company.objects.create(name='Acme Data', location='Cairo')
        Job.objects.create(
            title='Senior Django Engineer',
            company=company,
            location='Remote',
            description='Build APIs with Python and Django.',
            requirement='Strong Django experience.',
            job_url='https://example.com/django-role',
            job_type='Full-time',
        )
        Job.objects.create(
            title='Data Analyst',
            company=company,
            location='Cairo',
            description='Analyze product data.',
            requirement='SQL experience.',
            job_url='https://example.com/data-role',
            job_type='Contract',
            source='Bayt',
        )

    def test_homepage_renders(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Find work worth')
        self.assertContains(response, 'images/favicon.svg')
        self.assertContains(response, 'property="og:image"')
        self.assertContains(response, 'name="twitter:card"')

    def test_searches_title_company_location_and_type(self):
        response = self.client.get(reverse('job_list'), {
            'q': 'Acme',
            'location': 'Remote',
            'job_type': 'Full-time',
        })
        self.assertContains(response, 'Senior Django Engineer')
        self.assertNotContains(response, 'Data Analyst')

    def test_job_detail_renders(self):
        job = Job.objects.get(title='Senior Django Engineer')
        response = self.client.get(reverse('job_detail', args=[job.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Build APIs with Python and Django.')

    def test_filters_by_source(self):
        response = self.client.get(reverse('job_list'), {'source': 'Bayt'})
        self.assertContains(response, 'Data Analyst')
        self.assertNotContains(response, 'Senior Django Engineer')

    def test_subscription_form_creates_alert(self):
        response = self.client.post(reverse('subscribe'), {'email': 'dev@example.com'})
        self.assertRedirects(response, reverse('index'))
        self.assertTrue(EmailSubscription.objects.filter(email='dev@example.com').exists())
