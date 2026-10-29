from django.core import mail
from django.test import TestCase

from jobs.models import EmailSubscription
from jobs.tasks import send_welcome_email


class SubscriptionTest(TestCase):
    def setUp(self):
        mail.outbox = []

    def test_welcome_email_sent(self):
        subscription = EmailSubscription.objects.create(email='test@example.com')
        send_welcome_email(subscription.id)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Welcome to MENA Tech Careers job alerts')
        self.assertEqual(mail.outbox[0].to, ['test@example.com'])

    def test_welcome_email_not_sent_twice(self):
        subscription = EmailSubscription.objects.create(email='test@example.com')
        send_welcome_email(subscription.id)
        send_welcome_email(subscription.id)
        self.assertEqual(len(mail.outbox), 1)

    def test_inactive_subscription(self):
        subscription = EmailSubscription.objects.create(email='test@example.com', is_active=False)
        send_welcome_email(subscription.id)
        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_email(self):
        with self.assertRaises(Exception):
            EmailSubscription.objects.create(email='invalid-email')
