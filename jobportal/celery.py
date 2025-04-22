from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jobportal.settings')

app = Celery('jobportal')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Configure periodic tasks
app.conf.beat_schedule = {
    'scrape-jobs': {
        'task': 'jobs.tasks.scrape_jobs',
        'schedule': crontab(hour=8, minute=0),  # تشغيل الساعة 8 صباحاً
    },
    'update-jobs': {
        'task': 'jobs.tasks.update_jobs',
        'schedule': crontab(hour=8, minute=5),  # تشغيل الساعة 8:05 صباحاً
    },
    'scrape-and-import-jobs-daily': {
        'task': 'jobs.tasks.scrape_and_import_jobs',
        'schedule': crontab(hour=0, minute=0),  # Run at midnight (12 AM)
    },
    'update-jobs-daily': {
        'task': 'jobs.tasks.update_jobs',
        'schedule': crontab(hour=0, minute=0),  # Run at midnight every day
    },
    'cleanup-old-jobs-weekly': {
        'task': 'jobs.tasks.cleanup_old_jobs',
        'schedule': crontab(day_of_week='sunday', hour=0, minute=0),  # Run every Sunday at midnight
    },
}

# Windows-specific settings
if os.name == 'nt':  # Windows
    app.conf.update(
        worker_pool='solo',  # Use solo pool instead of prefork
        worker_concurrency=1,  # Run single worker
        broker_connection_retry_on_startup=True,  # Retry connection on startup
    )

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')