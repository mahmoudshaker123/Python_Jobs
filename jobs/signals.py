from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Job, EmailSubscription
from .tasks import send_job_notifications, send_welcome_email
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Job)
def notify_subscribers(sender, instance, created, **kwargs):
    if created and not settings.CELERY_TASK_ALWAYS_EAGER:
        try:
            send_job_notifications.delay(instance.id)
        except Exception as exc:
            logger.warning('Job notification queue is unavailable: %s', exc)

@receiver(post_save, sender=EmailSubscription)
def send_welcome_email_on_subscription(sender, instance, created, **kwargs):
    """
    Send welcome email when a new subscription is created
    """
    if created:
        try:
            if settings.CELERY_TASK_ALWAYS_EAGER:
                send_welcome_email(instance.id)
            else:
                send_welcome_email.delay(instance.id)
        except Exception as exc:
            logger.warning('Welcome email queue is unavailable: %s', exc)
