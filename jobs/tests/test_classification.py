from django.test import SimpleTestCase

from jobs.classification import classify_job
from jobs.models import Job


class JobClassificationTest(SimpleTestCase):
    def test_data_engineer_title_wins_over_enterprise_text(self):
        category, skills = classify_job(
            'Senior Data Engineer',
            'Build enterprise data platforms with Python, SQL and Spark.',
        )

        self.assertEqual(category, Job.Category.DATA_AI)
        self.assertIn('Python', skills)
        self.assertIn('SQL', skills)

    def test_erp_does_not_match_inside_enterprise(self):
        category, _ = classify_job(
            'Delivery Consultant',
            'Guide enterprise technology projects and implementation teams.',
        )

        self.assertEqual(category, Job.Category.OTHER)

    def test_explicit_erp_phrase_is_still_detected(self):
        category, _ = classify_job(
            'Implementation Consultant',
            'Lead ERP implementation and functional workshops.',
        )

        self.assertEqual(category, Job.Category.ODOO_ERP)
