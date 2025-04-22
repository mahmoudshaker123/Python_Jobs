from celery import shared_task
import requests
from bs4 import BeautifulSoup
from .models import Job, Company, EmailSubscription
from django.core.management import call_command
from datetime import datetime, timedelta
import os
from .scrapers import scrape_indeed, scrape_linkedin, scrape_glassdoor, get_random_job_data
from django.utils import timezone
import logging
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
import time

logger = logging.getLogger(__name__)

@shared_task
def scrape_jobs():
    """
    Task to scrape jobs from multiple sources
    """
    try:
        # For testing purposes, generate random job data
        job_data = get_random_job_data()
        
        # Create or update the job
        Job.objects.update_or_create(
            job_url=job_data['job_url'],
            defaults={
                'title': job_data['title'],
                'company': job_data['company'],
                'location': job_data['location'],
                'description': job_data['description'],
                'requirement': job_data['requirement'],
                'posted_at': job_data['posted_at'],
                'source': 'Test'
            }
        )

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
        # Step 1: Scrape new jobs
        scrape_result = scrape_wuzzuf_jobs.delay()
        time.sleep(5)  # Wait for scraping to complete
        
        # Step 2: Import the scraped jobs
        import_result = import_jobs_from_csv.delay()
        time.sleep(5)  # Wait for import to complete
        
        # Step 3: Clean up old jobs
        cleanup_result = cleanup_old_jobs.delay()
        
        return {
            "scrape_result": scrape_result.get(),
            "import_result": import_result.get(),
            "cleanup_result": cleanup_result.get()
        }
    except Exception as e:
        return f"Error updating jobs: {str(e)}"

@shared_task
def cleanup_old_jobs():
    """
    Task to remove jobs older than 30 days
    """
    try:
        thirty_days_ago = datetime.now() - timedelta(days=30)
        old_jobs = Job.objects.filter(created_at__lt=thirty_days_ago)
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
        # Step 1: Scrape jobs from Wuzzuf
        scrape_result = scrape_wuzzuf_jobs.delay()
        time.sleep(5)  # Wait for scraping to complete
        
        # Step 2: Import jobs from CSV
        import_result = import_jobs_from_csv.delay()
        
        return {
            "scrape_result": scrape_result.get(),
            "import_result": import_result.get()
        }
    except Exception as e:
        return f"Error in scrape_and_import_jobs: {str(e)}"

@shared_task
def send_job_notifications(job_id):
    """
    Send email notifications about new jobs to all subscribers
    """
    try:
        job = Job.objects.get(id=job_id)
        subscribers = EmailSubscription.objects.filter(is_active=True)
        
        for subscriber in subscribers:
            # Prepare email content
            subject = f'New Job Alert: {job.title}'
            html_message = render_to_string('jobs/email/job_notification.html', {
                'job': job,
                'subscriber': subscriber,
            })
            plain_message = strip_tags(html_message)
            
            # Send email
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[subscriber.email],
                html_message=html_message,
                fail_silently=False,
            )
            
        logger.info(f"Job notifications sent successfully for job ID: {job_id}")
        return f"Notifications sent for job ID: {job_id}"
        
    except Exception as e:
        logger.error(f"Error sending job notifications: {str(e)}")
        raise

@shared_task
def send_daily_job_digest():
    """
    Send daily digest of new jobs to all subscribers
    """
    try:
        # Get jobs from the last 24 hours
        yesterday = timezone.now() - timedelta(days=1)
        new_jobs = Job.objects.filter(posted_at__gte=yesterday)
        
        if not new_jobs.exists():
            return "No new jobs to send in digest"
            
        subscribers = EmailSubscription.objects.filter(is_active=True)
        
        for subscriber in subscribers:
            # Prepare email content
            subject = 'Daily Job Digest'
            html_message = render_to_string('jobs/email/daily_digest.html', {
                'jobs': new_jobs,
                'subscriber': subscriber,
            })
            plain_message = strip_tags(html_message)
            
            # Send email
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[subscriber.email],
                html_message=html_message,
                fail_silently=False,
            )
            
        logger.info("Daily job digest sent successfully")
        return "Daily job digest sent"
        
    except Exception as e:
        logger.error(f"Error sending daily job digest: {str(e)}")
        raise

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
        
        if not subscriber.welcome_email_sent:
            subject = 'Welcome to Python Career Newsletter!'
            html_message = render_to_string('jobs/email/welcome_email.html', {
                'subscriber': subscriber,
            })
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[subscriber.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            # Mark the welcome email as sent
            subscriber.welcome_email_sent = True
            subscriber.save()
            
            logger.info(f"Welcome email sent to {subscriber.email}")
            return f"Welcome email sent to {subscriber.email}"
        else:
            return f"Welcome email already sent to {subscriber.email}"
            
    except EmailSubscription.DoesNotExist:
        logger.error(f"Subscriber with ID {subscriber_id} not found")
        return f"Subscriber with ID {subscriber_id} not found"
    except Exception as e:
        logger.error(f"Error sending welcome email: {str(e)}")
        return f"Error sending welcome email: {str(e)}"