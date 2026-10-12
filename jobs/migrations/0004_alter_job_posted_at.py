from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ('jobs', '0003_job_job_type_job_source'),
    ]

    operations = [
        migrations.AlterField(
            model_name='job',
            name='posted_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
