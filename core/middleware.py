from django.conf import settings
from django.http import JsonResponse


class PortalAvailabilityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, 'PORTAL_ENABLED', True) and request.path_info != '/health/':
            return JsonResponse(
                {'detail': 'Portal temporariamente indisponível.'},
                status=503,
            )
        return self.get_response(request)
