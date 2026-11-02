import hashlib
import secrets
import re
import uuid
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Avg, Count, F, Max, Min, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import CompanyReviewForm, CVMatchForm, SubscriberForm
from .matching import extract_cv_text, rank_jobs_for_cv
from .models import Company, CompanyReview, CompanyReviewVote, EmailSubscription, Job, Startup, StartupSyncRun
from .notifications import send_matching_alerts, send_unsent_welcome_emails
from .site_i18n import get_site_language
from .sync import run_job_update
from .startup_sync import run_startup_update

REVIEW_VOTER_COOKIE = 'mena_review_voter'


def _review_voter_hash(request):
    token = request.COOKIES.get(REVIEW_VOTER_COOKIE, '')
    try:
        uuid.UUID(token)
    except (ValueError, TypeError, AttributeError):
        return None
    return hashlib.sha256(token.encode('ascii')).hexdigest()


def _reviews_with_vote_counts(queryset, request):
    reviews = list(queryset.annotate(
        helpful_votes=Count('votes', filter=Q(votes__value=CompanyReviewVote.VoteType.HELPFUL)),
        inaccurate_votes=Count('votes', filter=Q(votes__value=CompanyReviewVote.VoteType.INACCURATE)),
    ))
    voter_hash = _review_voter_hash(request)
    if voter_hash and reviews:
        vote_map = dict(CompanyReviewVote.objects.filter(
            review_id__in=[review.pk for review in reviews], voter_hash=voter_hash,
        ).values_list('review_id', 'value'))
        for review in reviews:
            review.my_vote = vote_map.get(review.pk, '')
    else:
        for review in reviews:
            review.my_vote = ''
    return reviews


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


def company_list(request):
    query = request.GET.get('q', '').strip()
    sort = request.GET.get('sort', 'jobs').strip()
    reviewed_only = request.GET.get('reviewed') == '1'
    approved_reviews = Q(reviews__is_approved=True)
    companies = Company.objects.filter(job__isnull=False).exclude(
        name__in=Company.PLACEHOLDER_NAMES,
    ).annotate(
        open_jobs=Count('job', distinct=True),
        review_count=Count('reviews', filter=approved_reviews, distinct=True),
        average_rating=Avg('reviews__overall_rating', filter=approved_reviews),
    )
    if query:
        companies = companies.filter(
            Q(name__icontains=query)
            | Q(location__icontains=query)
            | Q(description__icontains=query)
            | Q(job__title__icontains=query)
        ).distinct()
    if reviewed_only:
        companies = companies.filter(review_count__gt=0)
    orderings = {
        'rating': (F('average_rating').desc(nulls_last=True), '-review_count', 'name'),
        'reviews': ('-review_count', '-open_jobs', 'name'),
        'name': ('name',),
        'jobs': ('-open_jobs', '-review_count', 'name'),
    }
    companies = companies.order_by(*orderings.get(sort, orderings['jobs']))
    query_params = request.GET.copy()
    query_params.pop('page', None)
    return render(request, 'companies.html', {
        'page_obj': Paginator(companies, 24).get_page(request.GET.get('page')),
        'company_query': query,
        'selected_sort': sort,
        'reviewed_only': reviewed_only,
        'filter_query': query_params.urlencode(),
    })


def company_detail(request, id, slug=None):
    company = get_object_or_404(
        Company.objects.filter(job__isnull=False).distinct(),
        pk=id,
    )
    jobs = company.job_set.order_by('-posted_at')
    reviews = company.reviews.filter(is_approved=True)
    visible_reviews = _reviews_with_vote_counts(reviews, request)
    review_stats = reviews.aggregate(
        count=Count('id'),
        average_rating=Avg('overall_rating'),
        average_interview=Avg('interview_rating'),
        average_response_days=Avg('response_days'),
    )
    recommendation_reviews = reviews.filter(would_recommend__isnull=False)
    recommendation_total = recommendation_reviews.count()
    recommendation_percent = round(
        recommendation_reviews.filter(would_recommend=True).count() * 100 / recommendation_total
    ) if recommendation_total else None
    salary_summaries = list(
        reviews.exclude(salary_currency='').values('salary_currency', 'salary_period')
        .annotate(
            report_count=Count('id'),
            salary_low=Min('salary_min'),
            salary_high=Max('salary_max'),
        ).order_by('-report_count', 'salary_currency')
    )
    interview_outcomes = list(
        reviews.exclude(interview_outcome='').values('interview_outcome')
        .annotate(count=Count('id')).order_by('-count')
    )
    outcome_labels = dict(CompanyReview.InterviewOutcome.choices)
    for outcome in interview_outcomes:
        outcome['label'] = outcome_labels.get(outcome['interview_outcome'], outcome['interview_outcome'])
    categories = list(
        jobs.values('category').annotate(count=Count('id')).order_by('-count')[:5]
    )
    category_labels = dict(Job.Category.choices)
    for category in categories:
        category['label'] = category_labels.get(category['category'], category['category'])
    return render(request, 'company_detail.html', {
        'company': company,
        'jobs': jobs[:20],
        'job_count': jobs.count(),
        'reviews': visible_reviews[:12],
        'review_stats': review_stats,
        'recommendation_percent': recommendation_percent,
        'salary_summaries': salary_summaries,
        'interview_outcomes': interview_outcomes,
        'categories': categories,
    })


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
                jobs = Job.objects.select_related('company').order_by('-posted_at')[:600]
                matches = rank_jobs_for_cv(cv_text, jobs)
        except Exception:
            extraction_error = 'This file could not be read safely. Try exporting the CV as a text-based PDF.'
    return render(request, 'cv_match.html', {
        'form': form,
        'matches': matches,
        'extraction_error': extraction_error,
    })


def company_reviews(request):
    company_id = request.GET.get('company_id', '')
    initial = {'company': company_id} if company_id.isdigit() else None
    form = CompanyReviewForm(
        request.POST or None,
        initial=initial,
        language=get_site_language(request),
    )
    if request.method == 'POST':
        submitted_at = request.session.get('last_company_review_submission', 0)
        if timezone.now().timestamp() - submitted_at < 60:
            messages.error(request, 'Please wait a minute before submitting another review.')
        elif form.is_valid():
            review = form.save(commit=False)
            review.moderation_notes = moderation_reason(review)
            review.is_approved = not bool(review.moderation_notes)
            review.save()
            request.session['last_company_review_submission'] = timezone.now().timestamp()
            if review.is_approved:
                messages.success(request, 'Thanks. Your review is now published.')
                target = reverse('company_reviews') + '?' + urlencode({'company': review.company.name})
                return redirect(f'{target}#review-{review.pk}')
            messages.success(request, 'Thanks. Your review was held for moderator review before publication.')
            return redirect(review.company.get_absolute_url())

    query = request.GET.get('company', '').strip()
    reviews = CompanyReview.objects.filter(is_approved=True)
    if query:
        reviews = reviews.filter(company__name__icontains=query)
    reviews = _reviews_with_vote_counts(reviews.select_related('company'), request)
    summary = CompanyReview.objects.filter(is_approved=True).aggregate(
        review_count=Count('id'),
        company_count=Count('company', distinct=True),
        average_rating=Avg('overall_rating'),
    )
    return render(request, 'company_reviews.html', {
        'form': form,
        'page_obj': Paginator(reviews, 20).get_page(request.GET.get('page')),
        'company_query': query,
        'review_count': summary['review_count'] or 0,
        'company_count': summary['company_count'] or 0,
        'average_rating': summary['average_rating'],
    })


def company_review_vote(request, review_id):
    if request.method != 'POST':
        return redirect('company_reviews')
    review = get_object_or_404(CompanyReview, pk=review_id, is_approved=True)
    value = request.POST.get('vote', '')
    if value not in CompanyReviewVote.VoteType.values:
        messages.error(request, 'Choose whether this review was helpful or inaccurate.')
        return redirect('company_reviews')

    token = request.COOKIES.get(REVIEW_VOTER_COOKIE, '')
    try:
        uuid.UUID(token)
    except (ValueError, TypeError, AttributeError):
        token = str(uuid.uuid4())
    voter_hash = hashlib.sha256(token.encode('ascii')).hexdigest()
    CompanyReviewVote.objects.update_or_create(
        review=review, voter_hash=voter_hash, defaults={'value': value},
    )
    target = request.POST.get('next', '')
    if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        target = reverse('company_reviews')
    response = redirect(target)
    response.set_cookie(
        REVIEW_VOTER_COOKIE, token, max_age=31536000, httponly=True,
        secure=request.is_secure(), samesite='Lax',
    )
    return response


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
        'startup_sync': _latest_startup_run('jobs-scheduled-cron'),
        'finished_at': run.finished_at.isoformat() if run.finished_at else None,
    }, status=status_code)


def _latest_startup_run(trigger):
    run = StartupSyncRun.objects.filter(trigger=trigger).first()
    if not run:
        return None
    return {
        'status': run.status,
        'seen': run.startups_seen,
        'created': run.startups_created,
        'updated': run.startups_updated,
        'error': run.error or None,
    }


def cron_update_startups(request):
    expected = f'Bearer {settings.CRON_SECRET}'
    supplied = request.headers.get('Authorization', '')
    if not settings.CRON_SECRET or not secrets.compare_digest(supplied, expected):
        return JsonResponse({'ok': False, 'error': 'Unauthorized'}, status=401)
    try:
        run = run_startup_update(trigger='scheduled-cron')
    except Exception as exc:
        return JsonResponse({'ok': False, 'status': 'failed', 'error': str(exc)}, status=502)
    return JsonResponse({
        'ok': run.status in {'success', 'skipped'},
        'status': run.status,
        'run_id': run.pk,
        'startups_seen': run.startups_seen,
        'startups_created': run.startups_created,
        'startups_updated': run.startups_updated,
        'finished_at': run.finished_at.isoformat() if run.finished_at else None,
    }, status=202 if run.status == 'skipped' else 200)


def cron_send_alerts(request):
    expected = f'Bearer {settings.CRON_SECRET}'
    supplied = request.headers.get('Authorization', '')
    if not settings.CRON_SECRET or not secrets.compare_digest(supplied, expected):
        return JsonResponse({'ok': False, 'error': 'Unauthorized'}, status=401)
    welcome = send_unsent_welcome_emails(limit=settings.ALERT_BATCH_SIZE)
    alerts = send_matching_alerts(max_subscribers=settings.ALERT_BATCH_SIZE)
    return JsonResponse({'ok': alerts['failed'] == 0, 'welcome': welcome, 'alerts': alerts})
