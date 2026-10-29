import secrets

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import SubscriberForm
from .models import EmailSubscription, Job
from .notifications import send_matching_alerts, send_unsent_welcome_emails
from .sync import run_job_update


def index(request):
    jobs = Job.objects.select_related('company').order_by('-posted_at')[:6]
    category_counts = list(
        Job.objects.values('category').annotate(count=Count('id'))
        .order_by('-count')[:8]
    )
    category_labels = dict(Job.Category.choices)
    for item in category_counts:
        item['label'] = category_labels.get(item['category'], item['category'])
    return render(request, 'index.html', {
        'jobs': jobs,
        'jobs_count': Job.objects.count(),
        'companies_count': Job.objects.exclude(company=None).values('company').distinct().count(),
        'category_counts': category_counts,
    })


def job_list(request):
    search_title = request.GET.get('q', request.GET.get('title', '')).strip()
    search_location = request.GET.get('location', '').strip()
    job_type = request.GET.get('job_type', '').strip()
    source = request.GET.get('source', '').strip()
    category = request.GET.get('category', '').strip()

    jobs = Job.objects.select_related('company').order_by('-posted_at')
    if search_title:
        jobs = jobs.filter(
            Q(title__icontains=search_title)
            | Q(company__name__icontains=search_title)
            | Q(description__icontains=search_title)
        )
    if search_location and search_location != 'All Locations':
        jobs = jobs.filter(location__icontains=search_location)
    if job_type:
        jobs = jobs.filter(job_type=job_type)
    if source:
        jobs = jobs.filter(source=source)
    if category:
        jobs = jobs.filter(category=category)

    paginator = Paginator(jobs, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    query_params = request.GET.copy()
    query_params.pop('page', None)
    locations = (
        Job.objects.exclude(location='')
        .values_list('location', flat=True)
        .distinct()
        .order_by('location')
    )
    sources = (
        Job.objects.exclude(source='')
        .values_list('source', flat=True)
        .distinct()
        .order_by('source')
    )

    return render(request, 'job_list.html', {
        'page_obj': page_obj,
        'search_title': search_title,
        'search_location': search_location,
        'selected_job_type': job_type,
        'selected_source': source,
        'selected_category': category,
        'categories': Job.Category.choices,
        'job_types': Job.JOB_TYPE_CHOICES,
        'locations': locations,
        'sources': sources,
        'filter_query': query_params.urlencode(),
    })


def job_search(request):
    return job_list(request)


def job_detail(request, id):
    job = get_object_or_404(Job.objects.select_related('company'), id=id)
    return render(request, 'job_detail.html', {'job': job})


def subscribe(request):
    form = SubscriberForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            subscription = form.save()
            messages.success(
                request,
                f'Your tailored alerts are active for {subscription.email}.',
            )
            return redirect('index')
        messages.error(request, 'Please review the highlighted fields and try again.')
    return render(request, 'subscribe.html', {'form': form})


def manage_subscription(request, token):
    subscription = get_object_or_404(EmailSubscription, manage_token=token)
    initial = {
        'email': subscription.email,
        'categories': subscription.categories,
        'location_preference': subscription.location_preference,
        'job_types': subscription.job_types,
        'frequency': subscription.frequency,
    }
    form = SubscriberForm(request.POST or None, initial=initial, subscription=subscription)
    if request.method == 'POST' and form.is_valid():
        form.save(subscription=subscription)
        messages.success(request, 'Your alert preferences have been updated.')
        return redirect('manage_subscription', token=subscription.manage_token)
    return render(request, 'subscribe.html', {
        'form': form,
        'subscription': subscription,
        'is_manage': True,
    })


def unsubscribe(request, token):
    subscription = get_object_or_404(EmailSubscription, manage_token=token)
    if request.method == 'POST':
        subscription.is_active = False
        subscription.save(update_fields=('is_active',))
        messages.success(request, 'Job alerts have been turned off for this email.')
        return redirect('index')
    return render(request, 'unsubscribe.html', {'subscription': subscription})


def cron_update_jobs(request):
    expected = f'Bearer {settings.CRON_SECRET}'
    supplied = request.headers.get('Authorization', '')
    if not settings.CRON_SECRET or not secrets.compare_digest(supplied, expected):
        return JsonResponse({'ok': False, 'error': 'Unauthorized'}, status=401)

    try:
        run = run_job_update(trigger='scheduled-cron')
    except Exception as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=500)

    status_code = 202 if run.status == 'skipped' else 200
    return JsonResponse({
        'ok': run.status == 'success',
        'status': run.status,
        'run_id': run.pk,
        'expired_jobs_removed': run.jobs_removed,
        'finished_at': run.finished_at.isoformat() if run.finished_at else None,
    }, status=status_code)


def cron_send_alerts(request):
    expected = f'Bearer {settings.CRON_SECRET}'
    supplied = request.headers.get('Authorization', '')
    if not settings.CRON_SECRET or not secrets.compare_digest(supplied, expected):
        return JsonResponse({'ok': False, 'error': 'Unauthorized'}, status=401)
    welcome = send_unsent_welcome_emails(limit=settings.ALERT_BATCH_SIZE)
    alerts = send_matching_alerts(max_subscribers=settings.ALERT_BATCH_SIZE)
    return JsonResponse({'ok': alerts['failed'] == 0, 'welcome': welcome, 'alerts': alerts})
