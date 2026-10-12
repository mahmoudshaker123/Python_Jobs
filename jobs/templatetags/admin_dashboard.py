from datetime import timedelta

from django import template
from django.db.models import Q
from django.utils import timezone

from jobs.models import EmailSubscription, Job, JobSyncRun


register = template.Library()


@register.simple_tag
def dashboard_stats():
    since = timezone.now() - timedelta(hours=24)
    return {
        'jobs': Job.objects.count(),
        'new_jobs': Job.objects.filter(posted_at__gte=since).count(),
        'odoo_jobs': Job.objects.filter(
            Q(title__icontains='odoo') | Q(description__icontains='odoo')
        ).distinct().count(),
        'subscribers': EmailSubscription.objects.filter(is_active=True).count(),
        'latest_run': JobSyncRun.objects.first(),
        'recent_runs': JobSyncRun.objects.all()[:5],
    }
