from django import forms
from django.utils import timezone

from .models import EmailSubscription, Job


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
