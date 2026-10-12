from django.db import models
from django.core.validators import EmailValidator
from django.utils import timezone

class Company(models.Model):
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class Job(models.Model):
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

    def __str__(self):
        return self.title

class Subscriber(models.Model):
    email = models.EmailField(unique=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email

class EmailSubscription(models.Model):
    email = models.EmailField(unique=True, validators=[EmailValidator()])
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    welcome_email_sent = models.BooleanField(default=False)

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Email Subscription'
        verbose_name_plural = 'Email Subscriptions'


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
