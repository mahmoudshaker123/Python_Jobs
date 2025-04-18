import requests
from bs4 import BeautifulSoup
import csv
import os
import time
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Scrapes python and odoo jobs from Wuzzuf'

    def handle(self, *args, **kwargs):
        # إنشاء مجلد temp إذا لم يكن موجودًا
        temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'temp')
        os.makedirs(temp_dir, exist_ok=True)

        # تحديد مسار ملف CSV
        csv_file = os.path.join(temp_dir, 'all_jobs.csv')

        # إرسال طلب GET
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://wuzzuf.net/",
        }

        # فتح ملف CSV لتخزين البيانات
        try:
            with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(['Title', 'Company', 'Location', 'Link', 'Job Description', 'Job Requirements', 'Experience', 'Salary', 'Job Type'])

                # قائمة بالوظائف المطلوبة
                job_types = [
                    ('python', 'https://wuzzuf.net/search/jobs/?q=python&a=hpb'),
                    ('odoo', 'https://wuzzuf.net/search/jobs/?q=odoo%20developer&a=hpb')
                ]

                total_jobs_collected = 0
                target_jobs = 50

                for job_type, base_url in job_types:
                    self.stdout.write(f'\nجاري جمع وظائف {job_type}...')
                    page = 1

                    while total_jobs_collected < target_jobs:
                        # رابط صفحة نتائج البحث مع رقم الصفحة
                        url = f"{base_url}&start={page}"
                        
                        self.stdout.write(f'جاري تحميل الصفحة {page}...')

                        try:
                            response = requests.get(url, headers=headers)
                            response.raise_for_status()
                        except requests.RequestException as e:
                            self.stdout.write(self.style.ERROR(f'حدث خطأ في تحميل الصفحة: {str(e)}'))
                            break

                        # تحليل الصفحة باستخدام BeautifulSoup
                        soup = BeautifulSoup(response.text, 'html.parser')

                        # البحث عن جميع الروابط التي تحتوي على وظائف
                        job_links = soup.find_all('a', href=lambda x: x and '/jobs/p/' in x)
                        
                        if not job_links:
                            self.stdout.write(self.style.WARNING('لم يتم العثور على المزيد من الوظائف'))
                            break

                        self.stdout.write(self.style.SUCCESS(f'تم العثور على {len(job_links)} وظيفة في الصفحة {page}'))

                        # معالجة كل وظيفة
                        for index, link in enumerate(job_links, 1):
                            if total_jobs_collected >= target_jobs:
                                break

                            try:
                                job_url = "https://wuzzuf.net" + link['href'] if link['href'].startswith('/') else link['href']
                                title = link.text.strip()
                                
                                self.stdout.write(f'\nجاري معالجة الوظيفة {total_jobs_collected + 1} من {target_jobs}: {title}')
                                self.stdout.write(f'الرابط: {job_url}')

                                # الحصول على تفاصيل الوظيفة
                                try:
                                    job_response = requests.get(job_url, headers=headers)
                                    if job_response.status_code == 200:
                                        job_soup = BeautifulSoup(job_response.text, 'html.parser')
                                        
                                        # استخراج معلومات الشركة والموقع
                                        company = "Not available"
                                        location = "Not available"
                                        experience = "Not available"
                                        salary = "Not available"
                                        
                                        # البحث عن معلومات الشركة
                                        company_elem = job_soup.find('a', href=lambda x: x and '/jobs/careers/' in x)
                                        if company_elem:
                                            company = company_elem.text.strip().replace('-', '').strip()

                                        # البحث عن الموقع - تحسين البحث
                                        # أولاً: البحث في معلومات الوظيفة
                                        job_info_section = job_soup.find('div', {'class': 'css-1t5f0fr'})
                                        if job_info_section:
                                            # البحث عن عنصر الموقع
                                            location_elem = job_info_section.find(['div', 'span'], {'class': lambda x: x and 'css-' in x and 'location' in str(x).lower()})
                                            if location_elem:
                                                location = location_elem.text.strip()
                                            else:
                                                # البحث عن أي نص يحتوي على الموقع
                                                for elem in job_info_section.find_all(['div', 'span']):
                                                    text = elem.text.strip().lower()
                                                    if ('cairo' in text or 'egypt' in text) and not any(word in text for word in ['developer', 'engineer', 'specialist', 'manager']):
                                                        location = elem.text.strip()
                                                        break

                                        # إذا لم نجد الموقع في القسم الرئيسي، نبحث في باقي الصفحة
                                        if location == "Not available":
                                            location_elem = job_soup.find(['div', 'span'], string=lambda x: x and ('cairo' in str(x).lower() or 'egypt' in str(x).lower()))
                                            if location_elem and not any(word in location_elem.text.lower() for word in ['developer', 'engineer', 'specialist', 'manager']):
                                                location = location_elem.text.strip()

                                        # البحث عن الخبرة والراتب
                                        job_info = job_soup.find_all(['div', 'span'], {'class': lambda x: x and 'css-' in x})
                                        for info in job_info:
                                            text = info.text.strip()
                                            if 'experience' in text.lower():
                                                experience = text
                                            elif 'salary' in text.lower():
                                                salary = text

                                        # البحث عن الوصف والمتطلبات
                                        job_desc = "Not available"
                                        job_req = "Not available"
                                        
                                        # البحث عن قسم الوصف
                                        desc_section = job_soup.find('div', {'class': 'css-1t5f0fr'})
                                        if desc_section:
                                            # البحث عن جميع الفقرات في قسم الوصف
                                            paragraphs = desc_section.find_all('p')
                                            if paragraphs:
                                                job_desc = '\n'.join(p.text.strip() for p in paragraphs)
                                            else:
                                                job_desc = desc_section.text.strip()

                                        # البحث عن قسم المتطلبات
                                        req_section = job_soup.find('div', {'class': 'css-1t5f0fr'})
                                        if req_section:
                                            # البحث عن قائمة المتطلبات
                                            requirements_list = req_section.find_all('li')
                                            if requirements_list:
                                                job_req = '\n'.join(li.text.strip() for li in requirements_list)
                                            else:
                                                job_req = req_section.text.strip()

                                        # إذا لم نجد الأقسام بالطريقة السابقة، نبحث عن أي نص يحتوي على الكلمات المفتاحية
                                        if job_desc == "Not available":
                                            desc_elem = job_soup.find(['div', 'p', 'span'], string=lambda x: x and 'description' in str(x).lower())
                                            if desc_elem:
                                                job_desc = desc_elem.find_next(['div', 'p', 'span']).text.strip()

                                        if job_req == "Not available":
                                            req_elem = job_soup.find(['div', 'p', 'span'], string=lambda x: x and 'requirements' in str(x).lower())
                                            if req_elem:
                                                job_req = req_elem.find_next(['div', 'p', 'span', 'ul']).text.strip()

                                        # كتابة البيانات في الملف
                                        writer.writerow([title, company, location, job_url, job_desc, job_req, experience, salary, job_type])
                                        self.stdout.write(self.style.SUCCESS(f'تم حفظ بيانات الوظيفة {total_jobs_collected + 1}'))
                                        total_jobs_collected += 1

                                    else:
                                        self.stdout.write(self.style.WARNING(f'فشل في تحميل تفاصيل الوظيفة: {job_url}'))

                                except Exception as e:
                                    self.stdout.write(self.style.ERROR(f'خطأ في تحميل تفاصيل الوظيفة: {str(e)}'))

                                # إضافة تأخير لتجنب الحظر
                                time.sleep(2)

                            except Exception as e:
                                self.stdout.write(self.style.ERROR(f'خطأ في معالجة الوظيفة: {str(e)}'))
                                continue

                        page += 1
                        # إضافة تأخير بين الصفحات
                        time.sleep(3)

            self.stdout.write(self.style.SUCCESS(f'تم حفظ جميع البيانات في ملف {csv_file}'))
            self.stdout.write(self.style.SUCCESS(f'تم جمع {total_jobs_collected} وظيفة من أصل {target_jobs}'))

        except PermissionError:
            self.stdout.write(self.style.ERROR('خطأ في الوصول إلى الملف. يرجى التأكد من إغلاق الملف إذا كان مفتوحاً في برنامج آخر.'))
            return



        