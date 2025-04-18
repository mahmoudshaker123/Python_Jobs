from django.db import models
from django.utils import timezone

class Company(models.Model):
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class Job(models.Model):
    title = models.CharField(max_length=255)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='jobs')
    location = models.CharField(max_length=255)
    link = models.URLField(blank=True, null=True)
    description = models.TextField()
    requirements = models.TextField(blank=True, null=True)
    experience = models.CharField(max_length=255, blank=True, null=True)
    salary = models.CharField(max_length=255, blank=True, null=True)
    job_type = models.CharField(max_length=50, default='python')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['job_type']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.title} at {self.company.name}"

class Subscriber(models.Model):
    email = models.EmailField(unique=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email
