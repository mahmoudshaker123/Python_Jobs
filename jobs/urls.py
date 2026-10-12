from django.urls import path

from . import views


urlpatterns = [
    path('', views.index, name='index'),
    path('jobs/', views.job_list, name='job_list'),
    path('search/', views.job_search, name='job_search'),
    path('jobs/<int:id>/', views.job_detail, name='job_detail'),
    path('subscribe/', views.subscribe, name='subscribe'),
    path('api/cron/update-jobs/', views.cron_update_jobs, name='cron_update_jobs'),
]
