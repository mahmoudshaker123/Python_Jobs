from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.contrib import messages
from .models import Job
from .forms import SubscriberForm

def index(request):
    jobs = Job.objects.all().order_by('-posted_at')[:9]
    return render(request, 'index.html', {'jobs': jobs})

def job_list(request):
    jobs = Job.objects.all().order_by('-posted_at')
    paginator = Paginator(jobs, 12)  

    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'job_list.html', {'page_obj': page_obj})

def job_search(request):
    search_title = request.GET.get('title', '')
    search_location = request.GET.get('location', 'All Locations')

    # تصفية الوظائف بناءً على معايير البحث
    jobs = Job.objects.all().order_by('-posted_at')

    if search_title:
        jobs = jobs.filter(title__icontains=search_title)  # البحث في العنوان
    if search_location != 'All Locations':
        jobs = jobs.filter(location__icontains=search_location)  # البحث في الموقع

    paginator = Paginator(jobs, 12)  # عرض 12 وظيفة في كل صفحة
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # إرجاع استجابة تحتوي على الوظائف
    return render(request, 'job_list.html', {'page_obj': page_obj, 'search_title': search_title, 'search_location': search_location})

def job_detail(request, id):
    job = get_object_or_404(Job, id=id)
    return render(request, 'job_detail.html', {'job': job})

def subscribe(request):
    if request.method == 'POST':
        form = SubscriberForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'You have successfully subscribed!')
            return redirect('index')
    else:
        form = SubscriberForm()
    return render(request, 'subscribe.html', {'form': form})
