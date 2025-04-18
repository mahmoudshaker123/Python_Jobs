import csv
import os
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from jobs.models import Job, Company

class Command(BaseCommand):
    help = 'Updates jobs from CSV file and deactivates old jobs'

    def handle(self, *args, **kwargs):
        # مسار ملف CSV
        csv_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'temp', 'all_jobs.csv')

        if not os.path.exists(csv_file):
            self.stdout.write(self.style.ERROR('لم يتم العثور على ملف الوظائف'))
            return

        # قراءة الوظائف من ملف CSV
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            jobs_data = list(reader)

        # تحديث أو إضافة الوظائف
        for job_data in jobs_data:
            # البحث عن أو إنشاء الشركة
            company, _ = Company.objects.get_or_create(
                name=job_data['Company'],
                defaults={
                    'location': job_data['Location'],
                    'description': ''
                }
            )

            # البحث عن وظيفة موجودة بنفس الرابط
            job, created = Job.objects.get_or_create(
                link=job_data['Link'],
                defaults={
                    'title': job_data['Title'],
                    'company': company,
                    'location': job_data['Location'],
                    'description': job_data['Job Description'],
                    'requirements': job_data['Job Requirements'],
                    'experience': job_data['Experience'],
                    'salary': job_data['Salary'],
                    'job_type': job_data['Job Type'],
                    'is_active': True
                }
            )

            if not created:
                # تحديث الوظيفة الموجودة
                job.title = job_data['Title']
                job.company = company
                job.location = job_data['Location']
                job.description = job_data['Job Description']
                job.requirements = job_data['Job Requirements']
                job.experience = job_data['Experience']
                job.salary = job_data['Salary']
                job.job_type = job_data['Job Type']
                job.is_active = True
                job.save()

        # تعطيل الوظائف القديمة (التي لم يتم تحديثها في آخر 7 أيام)
        old_date = datetime.now() - timedelta(days=7)
        Job.objects.filter(updated_at__lt=old_date).update(is_active=False)

        self.stdout.write(self.style.SUCCESS('تم تحديث الوظائف بنجاح')) 