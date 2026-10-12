from django import forms
from .models import EmailSubscription

class SubscriberForm(forms.ModelForm):
    class Meta:
        model = EmailSubscription
        fields = ['email']
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'you@example.com',
                'autocomplete': 'email',
            })
        }
