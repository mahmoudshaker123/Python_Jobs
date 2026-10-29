import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

from .models import EmailSubscription, Job, JobAlertDelivery


logger = logging.getLogger(__name__)

ARAB_LOCATION_TERMS = (
    'egypt', 'cairo', 'alexandria', 'giza', 'saudi', 'riyadh', 'jeddah',
    'united arab emirates', 'uae', 'dubai', 'abu dhabi', 'qatar', 'doha',
    'kuwait', 'bahrain', 'oman', 'jordan', 'amman', 'lebanon', 'beirut',
    'iraq', 'morocco', 'tunisia', 'algeria', 'libya', 'palestine', 'yemen',
    'sudan', 'syria', 'mauritania',
)


def email_delivery_configured():
    backend = settings.EMAIL_BACKEND
    if backend.endswith('console.EmailBackend'):
        return False
    if backend.endswith('smtp.EmailBackend'):
        return bool(settings.EMAIL_HOST and settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD)
    return True


def _location_query(preference):
    if preference == EmailSubscription.LocationPreference.EGYPT:
        terms = ('egypt', 'cairo', 'alexandria', 'giza')
    elif preference == EmailSubscription.LocationPreference.ARAB:
        terms = ARAB_LOCATION_TERMS
    elif preference == EmailSubscription.LocationPreference.REMOTE:
        terms = ('remote', 'worldwide', 'anywhere', 'work from home')
    else:
        return Q()
    query = Q()
    for term in terms:
        query |= Q(location__icontains=term)
    return query


def _site_url():
    return settings.PUBLIC_SITE_URL.rstrip('/')


def send_welcome_email(subscription):
    if not subscription.is_active or subscription.welcome_email_sent:
        return False
    html = render_to_string('jobs/email/welcome_email.html', {
        'subscriber': subscription,
        'manage_url': f'{_site_url()}/alerts/{subscription.manage_token}/',
        'unsubscribe_url': f'{_site_url()}/alerts/{subscription.manage_token}/unsubscribe/',
    })
    send_mail(
        subject='Welcome to MENA Tech Careers job alerts',
        message=strip_tags(html),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[subscription.email],
        html_message=html,
        fail_silently=False,
    )
    subscription.welcome_email_sent = True
    subscription.last_email_error = ''
    subscription.save(update_fields=('welcome_email_sent', 'last_email_error'))
    return True


def send_unsent_welcome_emails(limit=20):
    stats = {'sent': 0, 'failed': 0, 'configured': email_delivery_configured()}
    if not stats['configured']:
        return stats
    subscriptions = EmailSubscription.objects.filter(
        is_active=True,
        welcome_email_sent=False,
    ).order_by('created_at')[:limit]
    for subscription in subscriptions:
        try:
            stats['sent'] += int(send_welcome_email(subscription))
        except Exception as exc:
            stats['failed'] += 1
            subscription.last_email_error = str(exc)[:2000]
            subscription.save(update_fields=('last_email_error',))
            logger.exception('Welcome email failed for subscription %s', subscription.pk)
    return stats


def _is_due(subscription, now):
    if not subscription.last_alert_sent_at:
        return True
    minimum_age = timedelta(
        hours=20 if subscription.frequency == EmailSubscription.Frequency.DAILY else 0.75
    )
    return subscription.last_alert_sent_at <= now - minimum_age


def _matching_jobs(subscription, limit=20):
    delivered = JobAlertDelivery.objects.filter(subscriber=subscription).values('job_id')
    jobs = Job.objects.filter(
        scraped_at__gte=subscription.alerts_started_at,
    ).exclude(pk__in=delivered).select_related('company').order_by('-posted_at')
    if subscription.categories:
        jobs = jobs.filter(category__in=subscription.categories)
    if subscription.job_types:
        jobs = jobs.filter(job_type__in=subscription.job_types)
    jobs = jobs.filter(_location_query(subscription.location_preference))
    return list(jobs[:limit])


def send_matching_alerts(max_subscribers=25, jobs_per_email=20):
    now = timezone.now()
    stats = {
        'subscribers': 0,
        'jobs': 0,
        'failed': 0,
        'configured': email_delivery_configured(),
    }
    if not stats['configured']:
        return stats
    subscribers = EmailSubscription.objects.filter(
        is_active=True,
        welcome_email_sent=True,
    ).order_by('last_alert_sent_at', 'created_at')
    for subscription in subscribers:
        if stats['subscribers'] >= max_subscribers or not _is_due(subscription, now):
            continue
        jobs = _matching_jobs(subscription, jobs_per_email)
        if not jobs:
            continue
        html = render_to_string('jobs/email/alert_digest.html', {
            'jobs': jobs,
            'subscriber': subscription,
            'manage_url': f'{_site_url()}/alerts/{subscription.manage_token}/',
            'unsubscribe_url': f'{_site_url()}/alerts/{subscription.manage_token}/unsubscribe/',
        })
        try:
            send_mail(
                subject=f'{len(jobs)} new tech job matches for you',
                message=strip_tags(html),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[subscription.email],
                html_message=html,
                fail_silently=False,
            )
            with transaction.atomic():
                JobAlertDelivery.objects.bulk_create(
                    [JobAlertDelivery(subscriber=subscription, job=job) for job in jobs],
                    ignore_conflicts=True,
                )
                subscription.last_alert_sent_at = now
                subscription.last_email_error = ''
                subscription.save(update_fields=('last_alert_sent_at', 'last_email_error'))
            stats['subscribers'] += 1
            stats['jobs'] += len(jobs)
        except Exception as exc:
            stats['failed'] += 1
            subscription.last_email_error = str(exc)[:2000]
            subscription.save(update_fields=('last_email_error',))
            logger.exception('Job alert failed for subscription %s', subscription.pk)
    return stats
