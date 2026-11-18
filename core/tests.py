import json
from unittest.mock import patch
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from .middleware import PortalAvailabilityMiddleware


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


class PortalAvailabilityMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get('/api/enrollments/list/')
        self.middleware = PortalAvailabilityMiddleware(lambda request: HttpResponse('ok'))

    @override_settings(PORTAL_ENABLED=False)
    def test_disabled_portal_returns_unavailable_without_calling_view(self):
        response = self.middleware(self.request)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            json.loads(response.content),
            {'detail': 'Portal temporariamente indisponível.'},
        )

    @override_settings(PORTAL_ENABLED=True)
    def test_enabled_portal_continues_to_view(self):
        response = self.middleware(self.request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'ok')

    @override_settings(PORTAL_ENABLED=False)
    def test_health_check_remains_available_when_portal_is_disabled(self):
        request = RequestFactory().get('/health/')
        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'ok')
