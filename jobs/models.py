import uuid

from django.db import models
from django.core.validators import EmailValidator
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

class Company(models.Model):
    PLACEHOLDER_NAMES = (
        'Unknown company', 'Company not disclosed', 'Direct advertiser',
        'Confidential', 'Confidential Company', 'Undisclosed',
    )

    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    website = models.URLField(max_length=500, blank=True)
    logo_url = models.URLField(max_length=500, blank=True)

    def __str__(self):
        return self.name

    @property
    def url_slug(self):
        return slugify(self.name) or 'company'

    def get_absolute_url(self):
        return reverse('company_detail', kwargs={'id': self.pk, 'slug': self.url_slug})

class Job(models.Model):
    class Category(models.TextChoices):
        SOFTWARE = 'software', 'Software Development'
        ODOO_ERP = 'odoo_erp', 'Odoo & ERP'
        DEVOPS = 'devops', 'DevOps & SRE'
        CLOUD = 'cloud', 'Cloud & Infrastructure'
        DATA_AI = 'data_ai', 'Data, BI & AI'
        IT_NETWORKS = 'it_networks', 'IT Support & Networking'
        CYBERSECURITY = 'cybersecurity', 'Cybersecurity'
        QA = 'qa', 'QA & Software Testing'
        PRODUCT = 'product', 'Product & Project Management'
        BUSINESS = 'business', 'Business Analysis'
        UI_UX = 'ui_ux', 'UI/UX Design'
        TECH_SALES = 'tech_sales', 'Technical Sales & Presales'
        OTHER = 'other', 'Other Technology Roles'

    JOB_TYPE_CHOICES = [
        ('Full-time', 'Full-time'),
        ('Part-time', 'Part-time'),
        ('Contract', 'Contract'),
        ('Internship', 'Internship'),
        ('Freelance', 'Freelance'),
    ]

    title = models.CharField(max_length=255)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    location = models.CharField(max_length=255)
    description = models.TextField()
    posted_at = models.DateTimeField(default=timezone.now)
    requirement = models.TextField(default='No requirements specified')
    job_url = models.URLField(max_length=200, default='')
    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES, default='Full-time')
    source = models.CharField(max_length=100, default='Wuzzuf', blank=True)
    category = models.CharField(
        max_length=30,
        choices=Category.choices,
        default=Category.OTHER,
        db_index=True,
    )
    skills = models.JSONField(default=list, blank=True)
    seniority = models.CharField(max_length=40, blank=True)
    salary_text = models.CharField(max_length=120, blank=True)
    is_remote = models.BooleanField(default=False, db_index=True)
    verified_at = models.DateTimeField(default=timezone.now)
    scraped_at = models.DateTimeField(default=timezone.now, db_index=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Startup(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True)
    country = models.CharField(max_length=100, blank=True, db_index=True)
    sectors = models.JSONField(default=list, blank=True)
    stage = models.CharField(max_length=80, blank=True, db_index=True)
    last_round = models.CharField(max_length=180, blank=True)
    total_raised = models.CharField(max_length=80, blank=True)
    investors = models.JSONField(default=list, blank=True)
    hiring_roles = models.PositiveIntegerField(default=0, db_index=True)
    logo_url = models.URLField(max_length=500, blank=True)
    source_url = models.URLField(max_length=500)
    source = models.CharField(max_length=100, default='Techny')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-hiring_roles', 'name')

    def __str__(self):
        return self.name

class CompanyReview(models.Model):
    class ExperienceType(models.TextChoices):
        EMPLOYEE = 'employee', 'Current employee'
        FORMER = 'former', 'Former employee'
        CANDIDATE = 'candidate', 'Interview candidate'

    class InterviewOutcome(models.TextChoices):
        OFFER = 'offer', 'Offer received'
        REJECTED = 'rejected', 'Rejected'
        NO_RESPONSE = 'no_response', 'No response'
        UNKNOWN = 'unknown', 'Prefer not to say'

    CURRENCY_CHOICES = [
        ('EGP', 'EGP'), ('SAR', 'SAR'), ('AED', 'AED'), ('USD', 'USD'),
        ('QAR', 'QAR'), ('KWD', 'KWD'), ('BHD', 'BHD'), ('OMR', 'OMR'),
        ('JOD', 'JOD'), ('MAD', 'MAD'), ('TND', 'TND'),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name='reviews',
    )
    role_title = models.CharField(max_length=180)
    country = models.CharField(max_length=80, blank=True)
    experience_type = models.CharField(max_length=20, choices=ExperienceType.choices)
    overall_rating = models.PositiveSmallIntegerField()
    interview_rating = models.PositiveSmallIntegerField(blank=True, null=True)
    would_recommend = models.BooleanField(blank=True, null=True)
    salary_min = models.PositiveIntegerField(blank=True, null=True)
    salary_max = models.PositiveIntegerField(blank=True, null=True)
    salary_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, blank=True)
    salary_period = models.CharField(max_length=12, blank=True)
    interview_process = models.TextField(blank=True, max_length=2500)
    pros = models.TextField(blank=True, max_length=1500)
    cons = models.TextField(blank=True, max_length=1500)
    response_days = models.PositiveSmallIntegerField(blank=True, null=True)
    interview_outcome = models.CharField(max_length=20, choices=InterviewOutcome.choices, blank=True)
    is_approved = models.BooleanField(default=False, db_index=True)
    moderation_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=('is_approved', 'company'), name='jobs_compan_is_appr_4d84cf_idx'),
            models.Index(fields=('is_approved', 'created_at'), name='jobs_compan_is_appr_b1ed23_idx'),
        ]

    def __str__(self):
        return f'{self.company.name} — {self.role_title}'


class CompanyReviewVote(models.Model):
    class VoteType(models.TextChoices):
        HELPFUL = 'helpful', 'Helpful'
        INACCURATE = 'inaccurate', 'Not accurate'

    review = models.ForeignKey(CompanyReview, on_delete=models.CASCADE, related_name='votes')
    voter_hash = models.CharField(max_length=64)
    value = models.CharField(max_length=12, choices=VoteType.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=('review', 'voter_hash'), name='unique_company_review_voter',
        )]
        indexes = [models.Index(fields=('review', 'value'), name='review_vote_count_idx')]


class StartupSyncState(models.Model):
    name = models.CharField(max_length=50, unique=True, default='startups')
    is_running = models.BooleanField(default=False)
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.name


class StartupSyncRun(models.Model):
    STATUS_CHOICES = [
        ('running', 'Running'), ('success', 'Success'),
        ('failed', 'Failed'), ('skipped', 'Skipped'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='running')
    trigger = models.CharField(max_length=50, default='manual')
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(blank=True, null=True)
    startups_seen = models.PositiveIntegerField(default=0)
    startups_created = models.PositiveIntegerField(default=0)
    startups_updated = models.PositiveIntegerField(default=0)
    output = models.TextField(blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ('-started_at',)
        verbose_name = 'Startup sync run'
        verbose_name_plural = 'Startup sync runs'


class Subscriber(models.Model):
    email = models.EmailField(unique=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email

class EmailSubscription(models.Model):
    class LocationPreference(models.TextChoices):
        ALL = 'all', 'All locations'
        EGYPT = 'egypt', 'Egypt'
        ARAB = 'arab', 'Arab countries'
        REMOTE = 'remote', 'Remote worldwide'

    class Frequency(models.TextChoices):
        HOURLY = 'hourly', 'Every hour'
        DAILY = 'daily', 'Daily digest'

    email = models.EmailField(unique=True, validators=[EmailValidator()])
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    welcome_email_sent = models.BooleanField(default=False)
    categories = models.JSONField(default=list, blank=True)
    job_types = models.JSONField(default=list, blank=True)
    location_preference = models.CharField(
        max_length=20,
        choices=LocationPreference.choices,
        default=LocationPreference.ALL,
    )
    frequency = models.CharField(
        max_length=20,
        choices=Frequency.choices,
        default=Frequency.DAILY,
    )
    manage_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    alerts_started_at = models.DateTimeField(default=timezone.now)
    last_alert_sent_at = models.DateTimeField(blank=True, null=True)
    last_email_error = models.TextField(blank=True)

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Email Subscription'
        verbose_name_plural = 'Email Subscriptions'


class JobAlertDelivery(models.Model):
    subscriber = models.ForeignKey(
        EmailSubscription,
        on_delete=models.CASCADE,
        related_name='deliveries',
    )
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='alert_deliveries')
    sent_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('subscriber', 'job'),
                name='unique_job_alert_delivery',
            ),
        ]
        ordering = ('-sent_at',)
        verbose_name = 'Job alert delivery'
        verbose_name_plural = 'Job alert deliveries'

    def __str__(self):
        return f'{self.subscriber.email} - {self.job.title}'


class JobSyncState(models.Model):
    name = models.CharField(max_length=50, unique=True, default='jobs')
    is_running = models.BooleanField(default=False)
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.name


class JobSyncRun(models.Model):
    STATUS_CHOICES = [
        ('running', 'Running'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    ]

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='running')
    trigger = models.CharField(max_length=50, default='manual')
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(blank=True, null=True)
    jobs_removed = models.PositiveIntegerField(default=0)
    output = models.TextField(blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ('-started_at',)
        verbose_name = 'Job sync run'
        verbose_name_plural = 'Job sync runs'

    def __str__(self):
        return f'{self.get_status_display()} — {self.started_at:%Y-%m-%d %H:%M}'
