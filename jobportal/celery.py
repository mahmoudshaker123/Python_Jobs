from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

# تعيين إعدادات Django الافتراضية
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jobportal.settings')

app = Celery('jobportal')

# استخدام إعدادات Django لتهيئة Celery
app.config_from_object('django.conf:settings', namespace='CELERY')

# تحميل المهام من جميع تطبيقات Django المسجلة
app.autodiscover_tasks()

# جدولة المهام
app.conf.beat_schedule = {
    'scrape-jobs': {
        'task': 'jobs.tasks.scrape_jobs',
        'schedule': crontab(hour=8, minute=0),  # تشغيل الساعة 8 صباحاً
    },
    'update-jobs': {
        'task': 'jobs.tasks.update_jobs',
        'schedule': crontab(hour=8, minute=5),  # تشغيل الساعة 8:05 صباحاً
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')