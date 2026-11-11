"""Production settings selected explicitly by the Render service."""
from urllib.parse import urlsplit
from django.core.exceptions import ImproperlyConfigured
from .settings import *  # noqa: F403

DEBUG = False
SECRET_KEY = os.environ.get('SECRET_KEY', '')
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith(('django-insecure-', 'sua_chave_')):
    raise ImproperlyConfigured('Configure uma SECRET_KEY de produção com pelo menos 50 caracteres.')

database_url = os.environ.get('DATABASE_URL', '')
if not database_url.startswith(('postgres://', 'postgresql://')):
    raise ImproperlyConfigured('O deploy exige DATABASE_URL de PostgreSQL; SQLite local não é permitido.')
DATABASES = {'default': dj_database_url.parse(database_url, conn_max_age=600, ssl_require=True)}

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])
render_hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if render_hostname:
    ALLOWED_HOSTS.append(render_hostname)
if not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured('Configure os hosts públicos exatos do backend.')

frontend_url = os.environ.get('FRONTEND_URL', '').rstrip('/')
parts = urlsplit(frontend_url)
if parts.scheme != 'https' or not parts.netloc or parts.path or parts.query or parts.fragment:
    raise ImproperlyConfigured('FRONTEND_URL deve ser uma origem HTTPS, sem caminho.')
CORS_ALLOWED_ORIGINS = [frontend_url]
CSRF_TRUSTED_ORIGINS = [frontend_url, *[f'https://{host}' for host in ALLOWED_HOSTS]]

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

MIDDLEWARE = list(MIDDLEWARE)
MIDDLEWARE.insert(MIDDLEWARE.index('django.middleware.security.SecurityMiddleware') + 1,
                  'whitenoise.middleware.WhiteNoiseMiddleware')
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

media_directory = os.environ.get('MEDIA_ROOT', '')
if not media_directory or not Path(media_directory).is_absolute():
    raise ImproperlyConfigured('Configure MEDIA_ROOT com o caminho absoluto do disco persistente.')
MEDIA_ROOT = media_directory
ROOT_URLCONF = 'core.render_urls'
