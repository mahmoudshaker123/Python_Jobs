from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('jobs', '0004_alter_job_posted_at')]

    operations = [
        migrations.CreateModel(
            name='JobSyncState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='jobs', max_length=50, unique=True)),
                ('is_running', models.BooleanField(default=False)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='JobSyncRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('running', 'Running'), ('success', 'Success'), ('failed', 'Failed'), ('skipped', 'Skipped')], default='running', max_length=20)),
                ('trigger', models.CharField(default='manual', max_length=50)),
                ('started_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('jobs_removed', models.PositiveIntegerField(default=0)),
                ('output', models.TextField(blank=True)),
                ('error', models.TextField(blank=True)),
            ],
            options={
                'verbose_name': 'Job sync run',
                'verbose_name_plural': 'Job sync runs',
                'ordering': ('-started_at',),
            },
        ),
    ]
