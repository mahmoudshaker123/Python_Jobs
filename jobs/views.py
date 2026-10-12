import secrets

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import SubscriberForm
from .models import Job
from .sync import run_job_update


def index(request):
    jobs = Job.objects.select_related('company').order_by('-posted_at')[:6]
    return render(request, 'index.html', {
        'jobs': jobs,
        'jobs_count': Job.objects.count(),
        'companies_count': Job.objects.exclude(company=None).values('company').distinct().count(),
    })


def job_list(request):
    search_title = request.GET.get('q', request.GET.get('title', '')).strip()
    search_location = request.GET.get('location', '').strip()
    job_type = request.GET.get('job_type', '').strip()
    source = request.GET.get('source', '').strip()

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
            form.save()
            messages.success(request, 'Welcome aboard! Your job alerts are now active.')
            return redirect('index')
        messages.error(request, 'Please check the email address and try again.')
    return render(request, 'subscribe.html', {'form': form})


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
