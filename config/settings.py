# config/settings.py

"""Zentrale Django-Einstellungen für das lokale Globi-Flow-Backend."""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent


def load_env_file() -> None:
    """Lädt lokale ENV-Dateien ohne zusätzliche Abhängigkeit."""
    environment = os.getenv('DJANGO_ENV', 'local').strip().lower()
    candidates = [BASE_DIR / '.env.prod'] if environment == 'production' else [BASE_DIR / '.env.local']
    candidates.append(BASE_DIR / '.env')

    for candidate in candidates:
        if candidate.exists():
            for raw_line in candidate.read_text(encoding='utf-8').splitlines():
                line = raw_line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)
            break


load_env_file()


def env_bool(name: str, default: bool = False) -> bool:
    """Liest eine boolesche Umgebungsvariable robust aus."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def env_int(name: str, default: int) -> int:
    """Liest eine Ganzzahl aus einer Umgebungsvariable."""
    value = os.getenv(name)
    if not value:
        return default
    return int(value)


def env_float(name: str, default: float) -> float:
    """Liest eine Fließkommazahl aus einer Umgebungsvariable."""
    value = os.getenv(name)
    if not value:
        return default
    return float(value)


def env_list(name: str, default: str = '') -> list[str]:
    """Liest eine komma-separierte Umgebungsvariable als Liste aus."""
    value = os.getenv(name, default)
    return [entry.strip() for entry in value.split(',') if entry.strip()]


def env_value(name: str, fallback_name: str, default: str = '') -> str:
    """Liest bevorzugt neue ENV-Namen und erlaubt alte Namen als Fallback."""
    return os.getenv(name, os.getenv(fallback_name, default))


def build_redis_url(database: int) -> str:
    """Baut eine Redis-URL aus den bestehenden Projekt-ENV-Konventionen."""
    host = os.getenv('REDIS_HOST', '127.0.0.1')
    port = os.getenv('REDIS_PORT', '6379')
    username = os.getenv('REDIS_USERNAME', '').strip()
    password = os.getenv('REDIS_PASSWORD', '').strip()
    use_acl = env_bool('REDIS_USE_ACL', False)

    if password and use_acl:
        user_part = username or 'default'
        return f'redis://{user_part}:{password}@{host}:{port}/{database}'
    if password:
        return f'redis://:{password}@{host}:{port}/{database}'
    return f'redis://{host}:{port}/{database}'


DJANGO_ENV = os.getenv('DJANGO_ENV', 'local')
SECRET_KEY = env_value('SECRET_KEY', 'DJANGO_SECRET_KEY', 'dev-only-change-me')
DEBUG = env_bool('DEBUG', env_bool('DJANGO_DEBUG', True))
ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost'))

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'apps.core',
    'apps.patients',
    'apps.labs',
    'apps.imports',
    'apps.knowledge',
    'apps.reports',
    'apps.dashboard',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env_value('DB_NAME', 'POSTGRES_DB', 'globi_flow'),
        'USER': env_value('DB_USER', 'POSTGRES_USER', 'globi_flow'),
        'PASSWORD': env_value('DB_PASSWORD', 'POSTGRES_PASSWORD', 'globi_flow_dev'),
        'HOST': env_value('DB_HOST', 'POSTGRES_HOST', '127.0.0.1'),
        'PORT': env_value('DB_PORT', 'POSTGRES_PORT', '5432'),
        'CONN_MAX_AGE': env_int('DB_CONN_MAX_AGE', 60),
        'OPTIONS': {'connect_timeout': env_int('DB_CONNECT_TIMEOUT', 5)},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'de-de'
TIME_ZONE = 'Europe/Berlin'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / os.getenv('MEDIA_ROOT', 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_PARSER_CLASSES': ['rest_framework.parsers.JSONParser', 'rest_framework.parsers.MultiPartParser', 'rest_framework.parsers.FormParser'],
    'DEFAULT_THROTTLE_RATES': {'upload': '20/hour'},
}

DEFAULT_LOCAL_ORIGINS = 'http://localhost:4200,http://127.0.0.1:4200,http://localhost:4300,http://127.0.0.1:4300,http://localhost:58652,http://127.0.0.1:58652'
CORS_ALLOWED_ORIGINS = env_list('CORS_ALLOWED_ORIGINS', os.getenv('DJANGO_CORS_ALLOWED_ORIGINS', DEFAULT_LOCAL_ORIGINS))
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS', ','.join(CORS_ALLOWED_ORIGINS))
CSRF_COOKIE_NAME = os.getenv('CSRF_COOKIE_NAME', 'XSRF-TOKEN')
CSRF_HEADER_NAME = os.getenv('CSRF_HEADER_NAME', 'HTTP_X_XSRF_TOKEN')

GLOBI_MAX_UPLOAD_MB = env_int('GLOBI_MAX_UPLOAD_MB', 12)
GLOBI_MAX_UPLOAD_BYTES = GLOBI_MAX_UPLOAD_MB * 1024 * 1024
GLOBI_USE_CELERY = env_bool('GLOBI_USE_CELERY', False)
TESSERACT_CMD = os.getenv('TESSERACT_CMD', '').strip()

REDIS_CHANNEL_DB = env_int('REDIS_CHANNEL_DB', 0)
REDIS_CACHE_DB = env_int('REDIS_CACHE_DB', 1)
REDIS_CELERY_DB = env_int('REDIS_CELERY_DB', 2)
REDIS_CELERY_RESULT_DB = env_int('REDIS_CELERY_RESULT_DB', 3)
REDIS_SOCKET_CONNECT_TIMEOUT = env_float('REDIS_SOCKET_CONNECT_TIMEOUT', 3.0)
REDIS_SOCKET_TIMEOUT = env_float('REDIS_SOCKET_TIMEOUT', 3.0)
REDIS_HEALTH_CHECK_INTERVAL = env_int('REDIS_HEALTH_CHECK_INTERVAL', 30)
REDIS_RETRY_ON_TIMEOUT = env_bool('REDIS_RETRY_ON_TIMEOUT', True)
REDIS_STRICT = env_bool('REDIS_STRICT', False)
REDIS_FALLBACK_INMEMORY = env_bool('REDIS_FALLBACK_INMEMORY', True)

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', build_redis_url(REDIS_CELERY_DB))
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', build_redis_url(REDIS_CELERY_RESULT_DB))
CELERY_TASK_ALWAYS_EAGER = not GLOBI_USE_CELERY
