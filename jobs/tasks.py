from celery import shared_task
import requests
from bs4 import BeautifulSoup
from .models import Job, Company

@shared_task
def fetch_python_jobs():
    url = 'https://wuzzuf.net/search/jobs/?q=python&a=hpb'
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # استخراج الوظائف من الصفحة
    job_listings = soup.find_all('div', class_='css-1gatmva e1v1l3u10')
    for job in job_listings:
        title = job.find('h2', class_='css-m604qf').text.strip()
        company_name = job.find('a', class_='css-17s97q8').text.strip()
        location = job.find('span', class_='css-5wys0k').text.strip()
        description = job.find('div', class_='css-y4udm8').text.strip()

        # إنشاء أو تحديث الشركة
        company, created = Company.objects.get_or_create(name=company_name)

        # إنشاء أو تحديث الوظيفة
        Job.objects.update_or_create(
            title=title,
            company=company,
            defaults={
                'location': location,
                'description': description,
            }
        )