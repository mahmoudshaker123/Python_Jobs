from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from jobs.models import Company, Job, JobSyncRun, JobSyncState


@override_settings(
    CRON_SECRET='test-cron-secret-123',
    JOB_SYNC_LIMIT=5,
    JOB_SYNC_DELAY=0,
    JOB_RETENTION_DAYS=30,
)
class CronUpdateTest(TestCase):
    def setUp(self):
        company = Company.objects.create(name='Old Company', location='Remote')
        self.expired_job = Job.objects.create(
            title='Expired Python role',
            company=company,
            location='Remote',
            description='Old role',
            requirement='Python',
            job_url='https://example.com/expired-role',
            posted_at=timezone.now() - timedelta(days=31),
        )

    def test_rejects_missing_secret(self):
        response = self.client.get(reverse('cron_update_jobs'))
        self.assertEqual(response.status_code, 401)

    @patch('jobs.sync.call_command')
    def test_runs_sync_and_removes_jobs_older_than_month(self, call_command_mock):
        response = self.client.get(
            reverse('cron_update_jobs'),
            HTTP_AUTHORIZATION='Bearer test-cron-secret-123',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Job.objects.filter(pk=self.expired_job.pk).exists())
        run = JobSyncRun.objects.get()
        self.assertEqual(run.status, 'success')
        self.assertEqual(run.jobs_removed, 1)
        call_command_mock.assert_called_once()
        self.assertTrue(call_command_mock.call_args.kwargs['keep_stale'])

    @patch('jobs.sync.call_command')
    def test_overlapping_run_is_skipped(self, call_command_mock):
        JobSyncState.objects.create(
            name='jobs', is_running=True, started_at=timezone.now(),
        )
        response = self.client.get(
            reverse('cron_update_jobs'),
            HTTP_AUTHORIZATION='Bearer test-cron-secret-123',
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()['status'], 'skipped')
        call_command_mock.assert_not_called()

    @patch('jobs.sync.call_command', side_effect=RuntimeError('source failure'))
    def test_cleanup_still_runs_when_scraping_fails(self, call_command_mock):
        response = self.client.get(
            reverse('cron_update_jobs'),
            HTTP_AUTHORIZATION='Bearer test-cron-secret-123',
        )
        self.assertEqual(response.status_code, 500)
        self.assertFalse(Job.objects.filter(pk=self.expired_job.pk).exists())
        run = JobSyncRun.objects.get()
        self.assertEqual(run.status, 'failed')
        self.assertEqual(run.jobs_removed, 1)

    def test_alert_cron_rejects_missing_secret(self):
        response = self.client.get(reverse('cron_send_alerts'))
        self.assertEqual(response.status_code, 401)

    @patch('jobs.views.send_matching_alerts', return_value={'subscribers': 2, 'jobs': 5, 'failed': 0, 'configured': True})
    @patch('jobs.views.send_unsent_welcome_emails', return_value={'sent': 1, 'failed': 0, 'configured': True})
    def test_alert_cron_sends_welcome_and_matching_batches(self, welcome_mock, alerts_mock):
        response = self.client.get(
            reverse('cron_send_alerts'),
            HTTP_AUTHORIZATION='Bearer test-cron-secret-123',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        welcome_mock.assert_called_once_with(limit=25)
        alerts_mock.assert_called_once_with(max_subscribers=25)


class AdminDashboardTest(TestCase):
    def test_custom_dashboard_renders(self):
        user = get_user_model().objects.create_superuser(
            username='admin', email='admin@example.com', password='password123',
        )
        self.client.force_login(user)
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Operations overview')
        self.assertContains(response, 'Recent syncs')
