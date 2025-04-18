import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Inspects the structure of Wuzzuf website'

    def handle(self, *args, **kwargs):
        # رابط صفحة نتائج البحث
        url = "https://wuzzuf.net/search/jobs/?q=python&a=hpb"

        # إرسال طلب GET
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://wuzzuf.net/",
        }

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f'حدث خطأ في تحميل الصفحة: {str(e)}'))
            return

        # تحليل الصفحة باستخدام BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')

        # حفظ HTML في ملف للفحص
        with open('wuzzuf_page.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        self.stdout.write(self.style.SUCCESS('تم حفظ HTML في ملف wuzzuf_page.html'))

        # البحث عن جميع العناصر div التي قد تحتوي على وظائف
        self.stdout.write(self.style.SUCCESS('\nالبحث عن عناصر الوظائف...'))
        job_containers = soup.find_all('div', {'data-testid': True})
        for container in job_containers:
            self.stdout.write(f'\nعنصر: {container.name}')
            self.stdout.write(f'data-testid: {container.get("data-testid")}')
            self.stdout.write(f'الفئات: {container.get("class", [])}')
            
            # البحث عن العنوان
            title = container.find(['h2', 'h3', 'a'])
            if title:
                self.stdout.write(f'العنوان: {title.text.strip()}')
            
            # البحث عن الشركة
            company = container.find(['div', 'span'], string=lambda text: text and 'company' in text.lower())
            if company:
                self.stdout.write(f'الشركة: {company.text.strip()}')
            
            # البحث عن الموقع
            location = container.find(['div', 'span'], string=lambda text: text and 'location' in text.lower())
            if location:
                self.stdout.write(f'الموقع: {location.text.strip()}')

        # البحث عن الروابط
        self.stdout.write(self.style.SUCCESS('\nالبحث عن الروابط...'))
        links = soup.find_all('a', href=True)
        for link in links:
            if '/jobs/' in link['href']:
                self.stdout.write(f'رابط: {link["href"]}')
                self.stdout.write(f'النص: {link.text.strip()}')

        # البحث عن الأقسام الرئيسية
        self.stdout.write(self.style.SUCCESS('\nالبحث عن الأقسام الرئيسية...'))
        sections = soup.find_all(['section', 'div'], {'role': True})
        for section in sections:
            self.stdout.write(f'\nقسم: {section.name}')
            self.stdout.write(f'الدور: {section.get("role")}')
            self.stdout.write(f'الفئات: {section.get("class", [])}') 