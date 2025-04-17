from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

# تعيين إعدادات Django كإعدادات افتراضية لـ Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jobportal.settings')

app = Celery('jobportal')

# استخدام إعدادات Django كإعدادات Celery
app.config_from_object('django.conf:settings', namespace='CELERY')

# اكتشاف المهام تلقائيًا في جميع التطبيقات المثبتة
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'fetch-jobs-every-hour': {
        'task': 'your_app_name.tasks.fetch_jobs',
        'schedule': crontab(minute=0, hour='*/1'),  # تشغيل المهمة كل ساعة
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')