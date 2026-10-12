from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('jobs', '0002_emailsubscription_welcome_email_sent'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='job_type',
            field=models.CharField(
                choices=[
                    ('Full-time', 'Full-time'),
                    ('Part-time', 'Part-time'),
                    ('Contract', 'Contract'),
                    ('Internship', 'Internship'),
                    ('Freelance', 'Freelance'),
                ],
                default='Full-time',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='job',
            name='source',
            field=models.CharField(blank=True, default='Wuzzuf', max_length=100),
        ),
    ]
