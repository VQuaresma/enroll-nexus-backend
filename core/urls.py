from django.contrib import admin
import re
from urllib.parse import urlsplit
from django.urls import path, include, re_path
from django.conf import settings
from rest_framework_simplejwt.views import (
    TokenRefreshView,
)
from configuracoes.views import AdminTokenObtainPairView
from enrollments.views import DocumentoArquivoView

urlpatterns = [
    path('admin/', admin.site.urls),  
    path('api/enrollments/', include('enrollments.urls')),
    path('api/token/', AdminTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/configuracoes/', include('configuracoes.urls')),
    re_path(
        r'^' + re.escape(urlsplit(settings.MEDIA_URL).path.lstrip('/')) + r'(?P<path>.*)$',
        DocumentoArquivoView.as_view(),
    ),
]
