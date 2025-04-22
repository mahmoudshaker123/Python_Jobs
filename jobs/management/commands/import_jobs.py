import csv
from django.core.management.base import BaseCommand
from django.db import transaction
from jobs.models import Job, Company
import re
from urllib.parse import urlparse

class Command(BaseCommand):
    help = 'Import jobs from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')

    def extract_company_name(self, url):
        try:
            # Parse the URL
            parsed_url = urlparse(url)
            path_parts = parsed_url.path.split('/')
            
            # Look for company name in the path
            for part in reversed(path_parts):
                if part and not part.isdigit():
                    # Remove common job-related words and special characters
                    company_name = re.sub(r'[^a-zA-Z0-9\s]', ' ', part)
                    company_name = ' '.join(word for word in company_name.split() 
                                         if word.lower() not in {
                                             'developer', 'engineer', 'administrator', 
                                             'manager', 'specialist', 'system', 'job',
                                             'jobs', 'career', 'careers', 'search',
                                             'view', 'apply', 'detail', 'details'
                                         })
                    if company_name and len(company_name) > 2:
                        return company_name.title()
            
            # If no company name found in path, try to extract from domain
            domain = parsed_url.netloc
            if domain:
                # Remove common domain parts
                domain = domain.replace('www.', '').replace('.com', '').replace('.org', '')
                if domain and len(domain) > 2:
                    return domain.title()
                
        except Exception:
            pass
            
        return "Unknown Company"

    def get_job_description(self, title, description, requirements):
        """Generate a detailed job description with Python-specific content."""
        if description and len(description) > 100:
            return description
            
        # Extract Python-related keywords from title
        title_lower = title.lower()
        python_keywords = {
            'python': 'Python programming',
            'django': 'Django web framework',
            'flask': 'Flask web framework',
            'fastapi': 'FastAPI framework',
            'pandas': 'Pandas data analysis',
            'numpy': 'NumPy scientific computing',
            'scikit-learn': 'scikit-learn machine learning',
            'tensorflow': 'TensorFlow deep learning',
            'pytorch': 'PyTorch deep learning',
            'data science': 'data science',
            'machine learning': 'machine learning',
            'backend': 'backend development',
            'api': 'API development',
            'web development': 'web development'
        }
        
        # Identify primary technology
        primary_tech = None
        for keyword, tech in python_keywords.items():
            if keyword in title_lower:
                primary_tech = tech
                break
                
        if not primary_tech:
            primary_tech = 'Python development'
            
        # Generate description based on primary technology
        base_description = f"""
        We are looking for a skilled {primary_tech} professional to join our team. 
        The ideal candidate will have strong experience in {primary_tech} and related technologies.
        
        Key Responsibilities:
        - Develop and maintain {primary_tech} applications
        - Write clean, efficient, and well-documented code
        - Collaborate with team members on software design and implementation
        - Implement best practices in software development
        - Participate in code reviews and technical discussions
        
        Required Skills:
        - Strong proficiency in {primary_tech}
        - Experience with version control systems
        - Understanding of software development best practices
        - Problem-solving and analytical skills
        """
        
        # Add specific requirements if provided
        if requirements:
            base_description += "\nAdditional Requirements:\n" + requirements
            
        return base_description.strip()

    def get_job_requirements(self, title, requirements):
        if requirements and requirements.strip() and requirements != "Not available":
            return requirements.strip()
        
        base_requirements = [
            "Strong problem-solving skills",
            "Excellent communication abilities",
            "Ability to work in a team environment",
            "Attention to detail",
            "Time management skills"
        ]
        
        # Add specific requirements based on job title
        title_lower = title.lower()
        if "python" in title_lower:
            base_requirements.extend([
                "Proficiency in Python programming",
                "Experience with Python frameworks (Django, Flask, etc.)",
                "Understanding of Python best practices and design patterns",
                "Knowledge of database systems and ORMs"
            ])
        elif "developer" in title_lower:
            base_requirements.extend([
                "Proficiency in programming languages",
                "Experience with software development",
                "Understanding of software design patterns",
                "Version control experience (Git)"
            ])
        elif "engineer" in title_lower:
            base_requirements.extend([
                "Strong analytical skills",
                "Experience with system design",
                "Knowledge of engineering principles",
                "Problem-solving abilities"
            ])
        
        return "\n".join(base_requirements)

    def is_duplicate_job(self, title, company, job_url):
        # Check for duplicates using multiple criteria
        return Job.objects.filter(
            title=title,
            company=company,
            job_url=job_url
        ).exists()

    def is_python_job(self, title, description, requirements):
        """Check if the job is Python-related."""
        python_keywords = {
            'python', 'django', 'flask', 'fastapi', 'pandas', 'numpy',
            'scikit-learn', 'tensorflow', 'pytorch', 'data science',
            'machine learning', 'backend', 'api', 'web development'
        }
        
        # Check title
        title_lower = title.lower()
        if any(keyword in title_lower for keyword in python_keywords):
            return True
            
        # Check description
        if description:
            desc_lower = description.lower()
            if any(keyword in desc_lower for keyword in python_keywords):
                return True
                
        # Check requirements
        if requirements:
            reqs_lower = ' '.join(requirements).lower()
            if any(keyword in reqs_lower for keyword in python_keywords):
                return True
                
        return False

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        try:
            with open(csv_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                total_jobs = 0
                imported_jobs = 0
                skipped_jobs = 0
                errors = 0
                
                for row in reader:
                    total_jobs += 1
                    try:
                        title = row.get('title', '').strip()
                        company = row.get('company', '').strip()
                        location = row.get('location', '').strip()
                        job_url = row.get('job_url', '').strip()
                        description = row.get('description', '').strip()
                        requirements = row.get('requirements', '').strip()
                        
                        # Skip if no title or URL
                        if not title or not job_url:
                            skipped_jobs += 1
                            continue
                            
                        # Skip if not a Python-related job
                        if not self.is_python_job(title, description, requirements):
                            skipped_jobs += 1
                            continue
                        
                        # Extract company name if not provided
                        if not company:
                            company = self.extract_company_name(job_url)
                            
                        # Skip if duplicate
                        if self.is_duplicate_job(title, company, job_url):
                            skipped_jobs += 1
                            continue
                            
                        # Create job entry
                        Job.objects.create(
                            title=title,
                            company=company,
                            location=location if location else "Not available",
                            job_url=job_url,
                            description=self.get_job_description(title, description, requirements),
                            requirements=self.get_job_requirements(title, requirements)
                        )
                        imported_jobs += 1
                        
                    except Exception as e:
                        self.stderr.write(self.style.ERROR(f'Error processing job: {str(e)}'))
                        errors += 1
                        
                self.stdout.write(self.style.SUCCESS(
                    f'Import complete. Total jobs: {total_jobs}, '
                    f'Imported: {imported_jobs}, '
                    f'Skipped: {skipped_jobs}, '
                    f'Errors: {errors}'
                ))
                
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f'File not found: {csv_file}')) 