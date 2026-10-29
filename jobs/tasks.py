from celery import shared_task
from .models import Job, EmailSubscription
from .notifications import (
    send_matching_alerts,
    send_welcome_email as deliver_welcome_email,
)
from django.core.management import call_command
from datetime import timedelta
import os
from django.utils import timezone
import logging
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

logger = logging.getLogger(__name__)

@shared_task
def scrape_jobs():
    """Refresh every configured source without deleting data from failed sources."""
    try:
        call_command('update_jobs')
        logger.info("Job scraping completed successfully")
        return "Job scraping completed successfully"

    except Exception as e:
        logger.error(f"Error in job scraping: {str(e)}")
        raise

@shared_task
def update_jobs():
    """
    Main task to update all jobs
    This task will:
    1. Scrape new jobs from Wuzzuf
    2. Import the scraped jobs
    3. Clean up old jobs
    """
    try:
        call_command('update_jobs')
        return {
            "scrape_result": "All sources refreshed",
            "cleanup_result": "Expired jobs removed during refresh",
        }
    except Exception as e:
        return f"Error updating jobs: {str(e)}"

@shared_task
def cleanup_old_jobs():
    """
    Task to remove jobs older than 30 days
    """
    try:
        thirty_days_ago = timezone.now() - timedelta(days=30)
        old_jobs = Job.objects.filter(posted_at__lt=thirty_days_ago)
        count = old_jobs.count()
        old_jobs.delete()
        return f"Successfully removed {count} old jobs"
    except Exception as e:
        return f"Error cleaning up old jobs: {str(e)}"

@shared_task
def scrape_and_import_jobs():
    """
    Task to scrape jobs from Wuzzuf and import them to the database
    """
    try:
        call_command('update_jobs')
        return {"scrape_result": "All sources refreshed and imported"}
    except Exception as e:
        return f"Error in scrape_and_import_jobs: {str(e)}"

@shared_task
def send_job_notifications(job_id):
    """
    Send email notifications about new jobs to all subscribers
    """
    Job.objects.get(id=job_id)
    return send_matching_alerts()

@shared_task
def send_daily_job_digest():
    """
    Send daily digest of new jobs to all subscribers
    """
    return send_matching_alerts()

@shared_task
def scrape_wuzzuf_jobs():
    """
    Task to scrape jobs from Wuzzuf and save them to a CSV file
    """
    try:
        # Call the scrape_wuzzuf management command
        call_command('scrape_wuzzuf')
        return "Successfully scraped jobs from Wuzzuf"
    except Exception as e:
        return f"Error scraping jobs from Wuzzuf: {str(e)}"

@shared_task
def import_jobs_from_csv():
    """
    Task to import jobs from the CSV file
    """
    try:
        # Get the path to the CSV file
        csv_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'temp', 'all_jobs.csv')
        
        # Call the import_jobs management command
        call_command('import_jobs', csv_file)
        return "Successfully imported jobs from CSV"
    except Exception as e:
        return f"Error importing jobs from CSV: {str(e)}"

@shared_task
def send_welcome_email(subscriber_id):
    """
    Send a welcome email to a new subscriber
    """
    try:
        subscriber = EmailSubscription.objects.get(id=subscriber_id)
        
        if not subscriber.is_active:
            return f"Subscription {subscriber.email} is inactive"

        sent = deliver_welcome_email(subscriber)
        return (
            f"Welcome email sent to {subscriber.email}"
            if sent else f"Welcome email already sent to {subscriber.email}"
        )
            
    except EmailSubscription.DoesNotExist:
        logger.error(f"Subscriber with ID {subscriber_id} not found")
        return f"Subscriber with ID {subscriber_id} not found"
    except Exception as e:
        logger.error(f"Error sending welcome email: {str(e)}")
        return f"Error sending welcome email: {str(e)}"
