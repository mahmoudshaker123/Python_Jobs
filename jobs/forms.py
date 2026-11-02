import re

from django import forms
from django.utils import timezone

from .models import Company, CompanyReview, EmailSubscription, Job


class SubscriberForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': 'form-control',
        'placeholder': 'you@example.com',
        'autocomplete': 'email',
    }))
    categories = forms.MultipleChoiceField(
        choices=Job.Category.choices,
        widget=forms.CheckboxSelectMultiple,
        help_text='Choose one or more fields.',
    )
    location_preference = forms.ChoiceField(
        choices=EmailSubscription.LocationPreference.choices,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    job_types = forms.MultipleChoiceField(
        choices=Job.JOB_TYPE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text='Leave all unchecked to receive every work type.',
    )
    frequency = forms.ChoiceField(
        choices=EmailSubscription.Frequency.choices,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, subscription=None, **kwargs):
        self.subscription = subscription
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if self.subscription:
            duplicate = EmailSubscription.objects.filter(email=email).exclude(pk=self.subscription.pk)
            if duplicate.exists():
                raise forms.ValidationError('This email already has a separate alert subscription.')
        return email

    def save(self, subscription=None):
        subscription = subscription or self.subscription
        email = self.cleaned_data['email'].lower()
        if subscription is None:
            subscription, _ = EmailSubscription.objects.get_or_create(email=email)
        was_active = subscription.is_active
        subscription.email = email
        subscription.categories = self.cleaned_data['categories']
        subscription.location_preference = self.cleaned_data['location_preference']
        subscription.job_types = self.cleaned_data['job_types']
        subscription.frequency = self.cleaned_data['frequency']
        subscription.is_active = True
        if not was_active:
            subscription.alerts_started_at = timezone.now()
        subscription.last_email_error = ''
        subscription.save()
        return subscription


class CVMatchForm(forms.Form):
    cv = forms.FileField(
        widget=forms.ClearableFileInput(attrs={
            'accept': '.pdf,.txt,application/pdf,text/plain',
            'class': 'cv-file-input',
            'aria-describedby': 'cv-file-help cv-file-name',
        }),
    )

    def clean_cv(self):
        upload = self.cleaned_data['cv']
        if upload.size > 5 * 1024 * 1024:
            raise forms.ValidationError('The CV must be 5 MB or smaller.')
        suffix = upload.name.lower().rsplit('.', 1)[-1] if '.' in upload.name else ''
        if suffix not in {'pdf', 'txt'}:
            raise forms.ValidationError('Upload a PDF or TXT file.')
        return upload


class CompanyReviewForm(forms.ModelForm):
    class CompanyChoiceField(forms.ModelChoiceField):
        def label_from_instance(self, obj):
            return f'{obj.name} — {obj.location}' if obj.location else obj.name

    company = CompanyChoiceField(
        queryset=Company.objects.none(),
        empty_label='Choose a company from the jobs directory',
        widget=forms.Select(attrs={'class': 'form-select review-company-select'}),
    )
    would_recommend = forms.ChoiceField(
        required=False,
        choices=(('', 'Select'), ('yes', 'Yes'), ('no', 'No')),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    website = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = CompanyReview
        fields = (
            'company', 'role_title', 'country', 'experience_type',
            'overall_rating', 'interview_rating', 'would_recommend',
            'salary_min', 'salary_max', 'salary_currency', 'salary_period',
            'interview_process', 'response_days', 'interview_outcome', 'pros', 'cons',
        )
        widgets = {
            'role_title': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'experience_type': forms.Select(attrs={'class': 'form-select'}),
            'overall_rating': forms.Select(choices=[(n, f'{n} / 5') for n in range(1, 6)], attrs={'class': 'form-select'}),
            'interview_rating': forms.Select(choices=[('', 'Skip'), *((n, f'{n} / 5') for n in range(1, 6))], attrs={'class': 'form-select'}),
            'salary_min': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'salary_max': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'salary_currency': forms.Select(attrs={'class': 'form-select'}),
            'salary_period': forms.Select(choices=(('', 'Skip'), ('monthly', 'Monthly'), ('yearly', 'Yearly')), attrs={'class': 'form-select'}),
            'interview_process': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'maxlength': 2500}),
            'response_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 365}),
            'interview_outcome': forms.Select(attrs={'class': 'form-select'}),
            'pros': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'maxlength': 1500}),
            'cons': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'maxlength': 1500}),
        }

    def __init__(self, *args, language='en', **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['company'].queryset = Company.objects.filter(
            job__isnull=False,
        ).exclude(
            name__in=Company.PLACEHOLDER_NAMES,
        ).distinct().order_by('name')
        if language == 'ar':
            self.fields['company'].empty_label = 'اختر شركة من دليل الوظائف'
            self.fields['experience_type'].choices = (
                ('', '---------'), ('employee', 'موظف حالي'),
                ('former', 'موظف سابق'), ('candidate', 'مرشح أجرى مقابلة'),
            )
            self.fields['interview_outcome'].choices = (
                ('', '---------'), ('offer', 'تم استلام عرض'), ('rejected', 'تم الرفض'),
                ('no_response', 'لم يصل رد'), ('unknown', 'أفضل عدم الإفصاح'),
            )
            self.fields['would_recommend'].choices = (
                ('', 'اختر'), ('yes', 'نعم'), ('no', 'لا'),
            )
            self.fields['salary_period'].choices = (
                ('', 'تخطي'), ('monthly', 'شهري'), ('yearly', 'سنوي'),
            )
            self.fields['interview_rating'].choices = (
                ('', 'تخطي'), *((n, f'{n} / 5') for n in range(1, 6)),
            )

    def clean_would_recommend(self):
        value = self.cleaned_data['would_recommend']
        return {'yes': True, 'no': False}.get(value)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('website'):
            raise forms.ValidationError('Submission could not be accepted.')
        minimum, maximum = cleaned.get('salary_min'), cleaned.get('salary_max')
        if minimum is not None and maximum is not None and minimum > maximum:
            self.add_error('salary_max', 'Maximum salary must be at least the minimum.')
        if (minimum is not None or maximum is not None) and not cleaned.get('salary_currency'):
            self.add_error('salary_currency', 'Choose the salary currency or leave salary blank.')

        contact_pattern = re.compile(
            r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|(?:https?://|www\.)\S+'
            r'|(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)',
            re.I,
        )
        for field in ('interview_process', 'pros', 'cons'):
            value = cleaned.get(field) or ''
            if contact_pattern.search(value):
                self.add_error(field, 'Do not include names, email addresses, phone numbers, or links.')
        return cleaned
