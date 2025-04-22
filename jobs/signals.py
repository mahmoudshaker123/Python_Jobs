from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Job, EmailSubscription
from .tasks import send_job_notifications, send_welcome_email

@receiver(post_save, sender=Job)
def notify_subscribers(sender, instance, created, **kwargs):
    if created:
        # Trigger the task to send notifications
        send_job_notifications.delay(instance.id)

@receiver(post_save, sender=EmailSubscription)
def send_welcome_email_on_subscription(sender, instance, created, **kwargs):
    """
    Send welcome email when a new subscription is created
    """
    if created:
        send_welcome_email.delay(instance.id) 