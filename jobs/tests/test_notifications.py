from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from jobs.models import Company, EmailSubscription, Job, JobAlertDelivery
from jobs.notifications import send_matching_alerts, send_welcome_email


@override_settings(PUBLIC_SITE_URL='https://example.com')
class NotificationMatchingTest(TestCase):
    def setUp(self):
        mail.outbox = []
        self.company = Company.objects.create(name='Cloud Co', location='Remote')
        self.subscription = EmailSubscription.objects.create(
            email='devops@example.com', categories=[Job.Category.DEVOPS],
            location_preference=EmailSubscription.LocationPreference.REMOTE,
            frequency=EmailSubscription.Frequency.HOURLY,
            alerts_started_at=timezone.now(),
        )
        send_welcome_email(self.subscription)
        mail.outbox = []

    def test_sends_only_matching_jobs_and_never_duplicates(self):
        matching = Job.objects.create(
            title='Senior DevOps Engineer', company=self.company, location='Remote - EMEA',
            description='Kubernetes and Terraform', requirement='AWS',
            job_url='https://example.com/devops', category=Job.Category.DEVOPS,
        )
        Job.objects.create(
            title='Data Analyst', company=self.company, location='Remote',
            description='SQL', requirement='Power BI',
            job_url='https://example.com/data', category=Job.Category.DATA_AI,
        )
        stats = send_matching_alerts()
        self.assertEqual(stats['subscribers'], 1)
        self.assertEqual(stats['jobs'], 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Senior DevOps Engineer', mail.outbox[0].body)
        self.assertEqual(JobAlertDelivery.objects.filter(job=matching).count(), 1)

        self.subscription.last_alert_sent_at = None
        self.subscription.save(update_fields=('last_alert_sent_at',))
        second = send_matching_alerts()
        self.assertEqual(second['jobs'], 0)
        self.assertEqual(len(mail.outbox), 1)
