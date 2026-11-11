from django.db import connection
from django.http import JsonResponse
from django.urls import path
from django.views.decorators.http import require_GET
from .urls import urlpatterns as application_urls


@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except Exception:
        return JsonResponse({'status': 'unavailable'}, status=503)
    return JsonResponse({'status': 'ok'})


urlpatterns = [path('health/', health), *application_urls]
