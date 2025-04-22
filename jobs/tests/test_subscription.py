from django.test import TestCase
from django.core import mail
from jobs.models import EmailSubscription
from jobs.tasks import send_welcome_email

class SubscriptionTest(TestCase):
    def setUp(self):
        # تنظيف صندوق البريد قبل كل اختبار
        mail.outbox = []

    def test_welcome_email_sent(self):
        # إنشاء اشتراك جديد
        subscription = EmailSubscription.objects.create(
            email='test@example.com',
            is_active=True
        )

        # التحقق من أن البريد الترحيبي تم إرساله
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Welcome to Python Career Newsletter!')
        self.assertEqual(mail.outbox[0].to, ['test@example.com'])

    def test_welcome_email_not_sent_twice(self):
        # إنشاء اشتراك جديد
        subscription = EmailSubscription.objects.create(
            email='test@example.com',
            is_active=True
        )

        # إرسال البريد الترحيبي يدوياً
        send_welcome_email(subscription.id)

        # التحقق من أن البريد لم يتم إرساله مرة أخرى
        self.assertEqual(len(mail.outbox), 1)

    def test_inactive_subscription(self):
        # إنشاء اشتراك غير نشط
        subscription = EmailSubscription.objects.create(
            email='test@example.com',
            is_active=False
        )

        # التحقق من أن البريد الترحيبي لم يتم إرساله
        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_email(self):
        # محاولة إنشاء اشتراك بريد إلكتروني غير صالح
        with self.assertRaises(Exception):
            EmailSubscription.objects.create(
                email='invalid-email',
                is_active=True
            ) 