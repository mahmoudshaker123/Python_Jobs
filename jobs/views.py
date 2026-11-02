import secrets
import re
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import CVMatchForm, SubscriberForm
from .matching import extract_cv_text, rank_jobs_for_cv
from .models import EmailSubscription, Job, Startup
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
        'sources_count': Job.objects.exclude(source='').values('source').distinct().count(),
        'hiring_startups': Startup.objects.filter(hiring_roles__gt=0)[:5],
    })


def job_list(request):
    search_title = request.GET.get('q', request.GET.get('title', '')).strip()
    search_location = request.GET.get('location', '').strip()
    job_type = request.GET.get('job_type', '').strip()
    source = request.GET.get('source', '').strip()
    category = request.GET.get('category', '').strip()
    seniority = request.GET.get('seniority', '').strip()
    posted = request.GET.get('posted', '').strip()
    remote = request.GET.get('remote', '').strip()

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
    if seniority:
        jobs = jobs.filter(seniority__iexact=seniority)
    if posted in {'7', '30', '90'}:
        jobs = jobs.filter(posted_at__gte=timezone.now() - timedelta(days=int(posted)))
    if remote == '1':
        jobs = jobs.filter(is_remote=True)

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
        'selected_seniority': seniority,
        'selected_posted': posted,
        'selected_remote': remote,
        'categories': Job.Category.choices,
        'job_types': Job.JOB_TYPE_CHOICES,
        'locations': locations,
        'sources': sources,
        'seniority_levels': ('Intern', 'Junior', 'Mid-level', 'Senior', 'Staff', 'Lead', 'Head'),
        'filter_query': query_params.urlencode(),
    })


def job_search(request):
    return job_list(request)


def job_detail(request, id):
    job = get_object_or_404(Job.objects.select_related('company'), id=id)
    similar_jobs = Job.objects.select_related('company').filter(
        category=job.category,
    ).exclude(pk=job.pk).order_by('-posted_at')[:4]
    return render(request, 'job_detail.html', {'job': job, 'similar_jobs': similar_jobs})


def startup_list(request):
    query = request.GET.get('q', '').strip().lower()
    country = request.GET.get('country', '').strip()
    stage = request.GET.get('stage', '').strip()
    sector = request.GET.get('sector', '').strip()
    hiring = request.GET.get('hiring', '').strip()

    all_startups = list(Startup.objects.all())
    sector_totals = {}
    for item in all_startups:
        for raw_sector in item.sectors or []:
            for value in re.split(r'[,;]', raw_sector):
                value = value.strip()
                if value and not value.lower().startswith('founded '):
                    sector_totals[value] = sector_totals.get(value, 0) + 1
    sector_distribution = [
        {'name': name, 'count': count}
        for name, count in sorted(sector_totals.items(), key=lambda pair: (-pair[1], pair[0]))[:6]
    ]
    sector_max = max((item['count'] for item in sector_distribution), default=1)
    for item in sector_distribution:
        item['width'] = max(8, round(item['count'] * 100 / sector_max))

    month_pattern = re.compile(
        r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(20\d{2})\b',
        re.IGNORECASE,
    )
    month_numbers = {name.lower(): number for number, name in enumerate(
        ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'), 1
    )}

    def round_sort_key(startup):
        match = month_pattern.search(startup.last_round or '')
        if not match:
            return (0, 0)
        return (int(match.group(2)), month_numbers[match.group(1)[:3].lower()])

    latest_rounds = sorted(
        (item for item in all_startups if item.last_round and item.last_round.lower() != 'not listed'),
        key=round_sort_key,
        reverse=True,
    )[:5]
    role_categories = list(
        Job.objects.values('category').annotate(count=Count('id')).order_by('-count')[:6]
    )
    category_labels = dict(Job.Category.choices)
    role_max = max((item['count'] for item in role_categories), default=1)
    for item in role_categories:
        item['label'] = category_labels.get(item['category'], item['category'])
        item['width'] = max(8, round(item['count'] * 100 / role_max))

    filtered = []
    for startup in all_startups:
        haystack = ' '.join((
            startup.name,
            startup.country,
            ' '.join(startup.sectors or []),
            ' '.join(startup.investors or []),
        )).lower()
        if query and query not in haystack:
            continue
        if country and startup.country != country:
            continue
        if stage and startup.stage != stage:
            continue
        if sector and sector not in (startup.sectors or []):
            continue
        if hiring == '1' and startup.hiring_roles <= 0:
            continue
        filtered.append(startup)

    page_obj = Paginator(filtered, 24).get_page(request.GET.get('page'))
    query_params = request.GET.copy()
    query_params.pop('page', None)
    return render(request, 'startups.html', {
        'page_obj': page_obj,
        'latest_rounds': latest_rounds,
        'sector_distribution': sector_distribution,
        'hiring_startups': [item for item in all_startups if item.hiring_roles > 0][:5],
        'role_categories': role_categories,
        'role_category_total': Job.objects.count(),
        'startup_count': len(all_startups),
        'hiring_count': sum(1 for item in all_startups if item.hiring_roles > 0),
        'country_count': len({item.country for item in all_startups if item.country}),
        'countries': sorted({item.country for item in all_startups if item.country}),
        'stages': sorted({item.stage for item in all_startups if item.stage and item.stage != 'Not listed'}),
        'sectors': sorted({value for item in all_startups for value in (item.sectors or [])}),
        'search_query': request.GET.get('q', ''),
        'selected_country': country,
        'selected_stage': stage,
        'selected_sector': sector,
        'selected_hiring': hiring,
        'filter_query': query_params.urlencode(),
    })


def cv_match(request):
    form = CVMatchForm(request.POST or None, request.FILES or None)
    matches = None
    extraction_error = ''
    if request.method == 'POST' and form.is_valid():
        try:
            cv_text = extract_cv_text(form.cleaned_data['cv'])
            if len(cv_text.strip()) < 80:
                extraction_error = 'We could not read enough text from this CV. Try a text-based PDF or TXT file.'
            else:
                jobs = Job.objects.select_related('company').order_by('-posted_at')[:300]
                matches = rank_jobs_for_cv(cv_text, jobs)
        except Exception:
            extraction_error = 'This file could not be read safely. Try exporting the CV as a text-based PDF.'
    return render(request, 'cv_match.html', {
        'form': form,
        'matches': matches,
        'extraction_error': extraction_error,
    })


def set_site_language(request, code):
    if code not in {'en', 'ar'}:
        code = 'en'
    request.session['site_language'] = code
    target = request.GET.get('next') or request.META.get('HTTP_REFERER') or '/'
    response = redirect(target)
    response.set_cookie('site_language', code, max_age=31536000, samesite='Lax')
    return response


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
