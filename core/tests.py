from unittest.mock import patch
from django.test import TestCase, override_settings


@override_settings(ROOT_URLCONF='core.render_urls')
class RenderHealthTests(TestCase):
    def test_health_checks_database_without_exposing_data(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_health_returns_503_without_internal_error_details(self):
        with patch('core.render_urls.connection.cursor', side_effect=RuntimeError('internal details')):
            response = self.client.get('/health/')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'unavailable'})

    def test_health_rejects_writes(self):
        self.assertEqual(self.client.post('/health/').status_code, 405)
