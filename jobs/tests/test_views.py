from django.test import TestCase
from django.urls import reverse

from django.core.files.uploadedfile import SimpleUploadedFile

from jobs.models import Company, CompanyReview, EmailSubscription, Job, Startup


class JobViewsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        company = Company.objects.create(name='Acme Data', location='Cairo')
        Job.objects.create(
            title='Senior Django Engineer', company=company, location='Remote',
            description='Build APIs with Python and Django.', requirement='Strong Django experience.',
            job_url='https://example.com/django-role', job_type='Full-time',
            category=Job.Category.SOFTWARE,
        )
        Job.objects.create(
            title='Data Analyst', company=company, location='Cairo',
            description='Analyze product data.', requirement='SQL experience.',
            job_url='https://example.com/data-role', job_type='Contract', source='Bayt',
            category=Job.Category.DATA_AI,
        )

    def test_homepage_renders(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tech careers, without the noise.')
        self.assertContains(response, 'MENA Tech Careers')
        self.assertContains(response, 'images/favicon.svg')
        self.assertContains(response, 'images/favicon-192.png')
        self.assertContains(response, 'https://menatechcareers.vercel.app/static/images/social-share.png')
        self.assertContains(response, 'property="og:image:width" content="1200"')
        self.assertContains(response, 'property="og:image:height" content="630"')
        self.assertContains(response, 'name="twitter:card"')
        self.assertContains(response, 'Mahmoud Shaker')
        self.assertContains(response, reverse('company_list'))

    def test_searches_title_company_location_and_type(self):
        response = self.client.get(reverse('job_list'), {
            'q': 'Acme', 'location': 'Remote', 'job_type': 'Full-time',
        })
        self.assertContains(response, 'Senior Django Engineer')
        self.assertNotContains(response, 'Data Analyst')

    def test_job_detail_renders(self):
        job = Job.objects.get(title='Senior Django Engineer')
        response = self.client.get(reverse('job_detail', args=[job.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Build APIs with Python and Django.')
        self.assertContains(response, job.company.get_absolute_url())

    def test_company_directory_links_jobs_reviews_and_profiles(self):
        company = Company.objects.get(name='Acme Data')
        hidden_company = Company.objects.create(name='No Jobs LLC', location='Cairo')
        CompanyReview.objects.create(
            company=company, role_title='Backend Engineer', country='Egypt',
            experience_type='employee', overall_rating=4, interview_rating=3,
            would_recommend=True, salary_min=30000, salary_max=45000,
            salary_currency='EGP', salary_period='monthly', response_days=7,
            interview_outcome='offer', pros='Supportive engineering team.',
            cons='The process could be faster.', is_approved=True,
        )
        CompanyReview.objects.create(
            company=company, role_title='Hidden review', experience_type='candidate',
            overall_rating=1, is_approved=False,
        )

        response = self.client.get(reverse('company_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Acme Data')
        self.assertContains(response, '2')
        self.assertNotContains(response, hidden_company.name)
        listed = response.context['page_obj'].object_list[0]
        self.assertEqual(listed.open_jobs, 2)
        self.assertEqual(listed.review_count, 1)

        response = self.client.get(company.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Senior Django Engineer')
        self.assertContains(response, 'Data Analyst')
        self.assertContains(response, 'Supportive engineering team.')
        self.assertNotContains(response, 'Hidden review')
        self.assertEqual(response.context['recommendation_percent'], 100)
        self.assertEqual(response.context['salary_summaries'][0]['salary_currency'], 'EGP')

    def test_company_directory_search_and_review_prefill(self):
        company = Company.objects.get(name='Acme Data')
        response = self.client.get(reverse('company_list'), {'q': 'Django'})
        self.assertContains(response, 'Acme Data')
        response = self.client.get(reverse('company_reviews'), {'company_id': company.pk})
        self.assertEqual(response.context['form'].initial['company'], str(company.pk))

    def test_filters_by_source(self):
        response = self.client.get(reverse('job_list'), {'source': 'Bayt'})
        self.assertContains(response, 'Data Analyst')
        self.assertNotContains(response, 'Senior Django Engineer')

    def test_filters_by_category(self):
        response = self.client.get(reverse('job_list'), {'category': Job.Category.DATA_AI})
        self.assertContains(response, 'Data Analyst')
        self.assertNotContains(response, 'Senior Django Engineer')

    def test_language_switch_sets_arabic_layout(self):
        response = self.client.get(reverse('set_site_language', args=['ar']), {'next': '/'})
        self.assertRedirects(response, '/')
        response = self.client.get(reverse('index'))
        self.assertContains(response, 'dir="rtl"')
        self.assertContains(response, 'وظائف تقنية')

    def test_startup_directory_filters_hiring_companies(self):
        Startup.objects.create(
            name='Cairo Cloud', slug='cairo-cloud', country='Egypt',
            sectors=['Cloud', 'SaaS'], stage='Seed', hiring_roles=4,
            source_url='https://techny.dev/companies/cairo-cloud',
        )
        Startup.objects.create(
            name='Quiet ERP', slug='quiet-erp', country='UAE',
            sectors=['ERP'], stage='Bootstrapped', hiring_roles=0,
            source_url='https://techny.dev/companies/quiet-erp',
        )
        response = self.client.get(reverse('startup_list'), {'hiring': '1'})
        self.assertContains(response, 'Cairo Cloud')
        self.assertNotContains(response, 'Quiet ERP')

    def test_cv_match_accepts_text_cv_without_storing_it(self):
        cv = SimpleUploadedFile(
            'mahmoud-cv.txt',
            (b'Python Django REST APIs PostgreSQL Docker cloud backend developer '
             b'with six years of software engineering experience and data integrations.'),
            content_type='text/plain',
        )
        response = self.client.post(reverse('cv_match'), {'cv': cv})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Senior Django Engineer')
        self.assertContains(response, 'Skills to strengthen')
        self.assertEqual(response.context['matches'][0]['job'].title, 'Senior Django Engineer')
        self.assertIn('experience', response.context['matches'][0]['reasons'])
        self.assertEqual(response.context['form'].files['cv'].name, 'mahmoud-cv.txt')

    def test_cv_match_prefers_the_relevant_career_track(self):
        cv = SimpleUploadedFile(
            'data-cv.txt',
            (b'Data analyst with four years of SQL, Tableau, Power BI, reporting, '
             b'dashboards, product analytics, data quality and stakeholder experience.'),
            content_type='text/plain',
        )
        response = self.client.post(reverse('cv_match'), {'cv': cv})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['matches'][0]['job'].title, 'Data Analyst')

    def test_cv_match_does_not_force_unrelated_results(self):
        cv = SimpleUploadedFile(
            'unrelated-cv.txt',
            (b'Experienced hospitality supervisor focused on restaurant operations, '
             b'guest satisfaction, food safety, inventory and shift scheduling for six years.'),
            content_type='text/plain',
        )
        response = self.client.post(reverse('cv_match'), {'cv': cv})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['matches'], [])

    def test_company_reviews_are_anonymous_and_hidden_until_moderated(self):
        response = self.client.get(reverse('company_reviews'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Submit anonymously')
        self.assertContains(response, 'Company reviews')

        payload = {
            'company': Company.objects.get(name='Acme Data').pk, 'role_title': 'Software Engineer',
            'country': 'Egypt', 'experience_type': 'candidate',
            'overall_rating': 4, 'interview_rating': 3, 'would_recommend': 'yes',
            'salary_min': '', 'salary_max': '', 'salary_currency': '', 'salary_period': '',
            'interview_process': 'Two technical rounds and a discussion with the team.',
            'response_days': 5, 'interview_outcome': 'offer',
            'pros': 'Friendly engineers and clear expectations.',
            'cons': 'The process took several weeks.', 'website': '',
        }
        response = self.client.post(reverse('company_reviews'), payload)
        company = Company.objects.get(name='Acme Data')
        self.assertRedirects(response, company.get_absolute_url())
        review = CompanyReview.objects.get()
        self.assertFalse(review.is_approved)
        self.assertFalse(CompanyReview.objects.filter(is_approved=True).exists())

        review.is_approved = True
        review.save(update_fields=('is_approved',))
        response = self.client.get(reverse('company_reviews'))
        self.assertContains(response, 'Acme Data')
        self.assertContains(response, 'Software Engineer')
        self.assertEqual(response.context['review_count'], 1)
        self.assertEqual(response.context['company_count'], 1)

    def test_company_review_form_localizes_choices_in_arabic(self):
        self.client.get(reverse('set_site_language', args=['ar']), {'next': reverse('company_reviews')})
        response = self.client.get(reverse('company_reviews'))
        self.assertContains(response, 'اختر شركة من دليل الوظائف')
        self.assertContains(response, 'مرشح أجرى مقابلة')

    def test_company_review_rejects_contact_details(self):
        response = self.client.post(reverse('company_reviews'), {
            'company': Company.objects.get(name='Acme Data').pk, 'role_title': 'Engineer',
            'experience_type': 'candidate', 'overall_rating': 4,
            'interview_process': 'Contact me at person@example.com',
            'website': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CompanyReview.objects.exists())

    def test_company_review_must_reference_a_company_with_jobs(self):
        company_without_jobs = Company.objects.create(name='Not Listed Employer', location='Egypt')
        response = self.client.post(reverse('company_reviews'), {
            'company': company_without_jobs.pk, 'role_title': 'Engineer',
            'experience_type': 'candidate', 'overall_rating': 4,
            'interview_process': 'A technical interview.', 'website': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context['form'], 'company',
            'Select a valid choice. That choice is not one of the available choices.',
        )
        self.assertFalse(CompanyReview.objects.exists())

    def test_subscription_form_creates_alert(self):
        response = self.client.post(reverse('subscribe'), {
            'email': 'dev@example.com', 'categories': ['software', 'data_ai'],
            'location_preference': 'arab', 'job_types': ['Full-time'], 'frequency': 'daily',
        })
        self.assertRedirects(response, reverse('index'))
        subscription = EmailSubscription.objects.get(email='dev@example.com')
        self.assertEqual(subscription.categories, ['software', 'data_ai'])
        self.assertEqual(subscription.location_preference, 'arab')

    def test_subscription_can_be_managed_and_disabled(self):
        subscription = EmailSubscription.objects.create(
            email='alerts@example.com', categories=['software'],
        )
        response = self.client.post(
            reverse('manage_subscription', args=[subscription.manage_token]),
            {
                'email': subscription.email, 'categories': ['devops'],
                'location_preference': 'remote', 'job_types': [], 'frequency': 'hourly',
            },
        )
        self.assertEqual(response.status_code, 302)
        subscription.refresh_from_db()
        self.assertEqual(subscription.categories, ['devops'])
        self.client.post(reverse('unsubscribe', args=[subscription.manage_token]))
        subscription.refresh_from_db()
        self.assertFalse(subscription.is_active)
