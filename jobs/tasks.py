from celery import shared_task
import requests
from bs4 import BeautifulSoup
from .models import Job, Company
from django.core.management import call_command
from datetime import datetime, timedelta



@shared_task
def scrape_jobs():
    """مهمة جمع الوظائف من Wuzzuf"""
    try:
        call_command('scrape_wuzzuf')
        return "تم جمع الوظائف بنجاح"
    except Exception as e:
        return f"حدث خطأ أثناء جمع الوظائف: {str(e)}"

@shared_task
def update_jobs():
    """مهمة تحديث الوظائف في قاعدة البيانات"""
    try:
        call_command('update_jobs')
        return "تم تحديث الوظائف بنجاح"
    except Exception as e:
        return f"حدث خطأ أثناء تحديث الوظائف: {str(e)}"

@shared_task
def cleanup_old_jobs():
    """مهمة تنظيف الوظائف القديمة"""
    try:
        # تعطيل الوظائف التي لم يتم تحديثها منذ 30 يوم
        old_date = datetime.now() - timedelta(days=30)
        Job.objects.filter(updated_at__lt=old_date).update(is_active=False)
        return "تم تنظيف الوظائف القديمة بنجاح"
    except Exception as e:
        return f"حدث خطأ أثناء تنظيف الوظائف القديمة: {str(e)}"