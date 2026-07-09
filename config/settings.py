# config/settings.py

"""
Zentrale Django-Einstellungen für das lokale Globi-Flow-Backend.

Dieses Settings-Modul enthält:
    - Konfiguration für Django, DRF, Daphne und optionale Celery-Verarbeitung
    - Sichere Defaults für Angular-Integration über CORS/CSRF
    - Lokale PDF-/OCR-Verarbeitung ohne externe Cloud-Dienste
    - Deutsche Lokalisierung und PostgreSQL-Anbindung
    - Saubere Struktur für DEV & PROD-Anpassungen

Empfohlen:
    - Für PROD Umgebungsvariablen über .env.prod oder OS setzen.
    - SECRET_KEY & Datenbankdaten niemals in öffentliche Repos committen.
    - Redis/Celery erst aktivieren, wenn der synchrone Import stabil läuft.
"""

from pathlib import Path
from urllib.parse import quote
import os


# ------------------------------------------------------------------------------
# Basisverzeichnisse & ENV-Laden
# ------------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

ENV = os.getenv("DJANGO_ENV", "local").strip().lower()

if ENV == "production":
    ENV_FILE = BASE_DIR / ".env.prod"
else:
    ENV_FILE = BASE_DIR / ".env.local"

FALLBACK_ENV_FILE = BASE_DIR / ".env"


def load_env_file() -> None:
    """Lädt lokale ENV-Dateien ohne zusätzliche Abhängigkeit."""
    candidates = [ENV_FILE, FALLBACK_ENV_FILE]

    for candidate in candidates:
        if not candidate.exists():
            continue

        for raw_line in candidate.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip().strip('"').strip("'")
        break


load_env_file()
ENV = os.getenv("DJANGO_ENV", ENV).strip().lower()


# ------------------------------------------------------------------------------
# ENV-Helfer
# ------------------------------------------------------------------------------


def env_bool(name: str, default: bool = False) -> bool:
    """Liest eine boolesche Umgebungsvariable robust aus."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    """Liest eine Ganzzahl aus einer Umgebungsvariable."""
    value = os.getenv(name)
    if not value:
        return default
    return int(float(value))


def env_float(name: str, default: float) -> float:
    """Liest eine Fließkommazahl aus einer Umgebungsvariable."""
    value = os.getenv(name)
    if not value:
        return default
    return float(value)


def env_list(name: str, default: str = "") -> list[str]:
    """Liest eine komma-separierte Umgebungsvariable als Liste aus."""
    value = os.getenv(name, default)
    return [entry.strip() for entry in value.split(",") if entry.strip()]


def env_path(name: str, default: str = "") -> str:
    """Liest einen lokalen Pfad und entfernt versehentliche Quotes."""
    return os.getenv(name, default).strip().strip('"').strip("'")


def env_value(name: str, fallback_name: str, default: str = "") -> str:
    """Liest bevorzugt neue ENV-Namen und erlaubt alte Namen als Fallback."""
    return os.getenv(name, os.getenv(fallback_name, default)).strip()


# ------------------------------------------------------------------------------
# SECRET_KEY, DEBUG, ALLOWED_HOSTS
# ------------------------------------------------------------------------------

SECRET_KEY = env_value("SECRET_KEY", "DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = env_bool("DEBUG", env_bool("DJANGO_DEBUG", True))

if ENV == "production":
    ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", os.getenv("DJANGO_ALLOWED_HOSTS", "localhost"))
else:
    ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "127.0.0.1,localhost")


# ------------------------------------------------------------------------------
# Apps & Middleware
# ------------------------------------------------------------------------------

INSTALLED_APPS = [
    "daphne",

    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "corsheaders",
    "rest_framework",

    "apps.core.apps.CoreConfig",
    "apps.patients.apps.PatientsConfig",
    "apps.labs.apps.LabsConfig",
    "apps.imports.apps.ImportsConfig",
    "apps.knowledge.apps.KnowledgeConfig",
    "apps.reports.apps.ReportsConfig",
    "apps.dashboard.apps.DashboardConfig",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ------------------------------------------------------------------------------
# CORS / CSRF für Angular
# ------------------------------------------------------------------------------

DEFAULT_LOCAL_ORIGINS = (
    "http://localhost:4200,"
    "http://127.0.0.1:4200,"
    "http://localhost:4300,"
    "http://127.0.0.1:4300,"
    "http://localhost:58652,"
    "http://127.0.0.1:58652"
)

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    os.getenv("DJANGO_CORS_ALLOWED_ORIGINS", DEFAULT_LOCAL_ORIGINS),
)
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", ",".join(CORS_ALLOWED_ORIGINS))
CSRF_COOKIE_NAME = os.getenv("CSRF_COOKIE_NAME", "XSRF-TOKEN")
CSRF_HEADER_NAME = os.getenv("CSRF_HEADER_NAME", "HTTP_X_XSRF_TOKEN")
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"

if ENV == "production":
    CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", True)
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", True)
else:
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False


# ------------------------------------------------------------------------------
# REST Framework
# ------------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "upload": "20/hour",
    },
}


# ------------------------------------------------------------------------------
# Routing/URLs/Templates
# ------------------------------------------------------------------------------

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# ------------------------------------------------------------------------------
# Datenbank
# ------------------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env_value("DB_NAME", "POSTGRES_DB", "globi_flow_db"),
        "USER": env_value("DB_USER", "POSTGRES_USER", "globi_flow_admin"),
        "PASSWORD": env_value("DB_PASSWORD", "POSTGRES_PASSWORD", ""),
        "HOST": env_value("DB_HOST", "POSTGRES_HOST", "127.0.0.1"),
        "PORT": env_value("DB_PORT", "POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 60),
        "OPTIONS": {
            "connect_timeout": env_int("DB_CONNECT_TIMEOUT", 5),
        },
    }
}


# ------------------------------------------------------------------------------
# Passwort-Validierung
# ------------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ------------------------------------------------------------------------------
# Lokalisierung/Zeitzone
# ------------------------------------------------------------------------------

LANGUAGE_CODE = "de-de"
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_TZ = True


# ------------------------------------------------------------------------------
# Statische Dateien & lokale Medien
# ------------------------------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env_path("MEDIA_ROOT", str(BASE_DIR / "media")))
if not MEDIA_ROOT.is_absolute():
    MEDIA_ROOT = BASE_DIR / MEDIA_ROOT

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ------------------------------------------------------------------------------
# Globi Flow: Upload, PDF-Analyse und lokale OCR
# ------------------------------------------------------------------------------

GLOBI_MAX_UPLOAD_MB = env_int("GLOBI_MAX_UPLOAD_MB", 12)
GLOBI_MAX_UPLOAD_BYTES = GLOBI_MAX_UPLOAD_MB * 1024 * 1024
GLOBI_USE_CELERY = env_bool("GLOBI_USE_CELERY", False)
IMPORT_AUTO_REVIEW_CONFIDENCE_THRESHOLD = env_int("IMPORT_AUTO_REVIEW_CONFIDENCE_THRESHOLD", 90)

OCR_ENABLED = env_bool("OCR_ENABLED", True)
OCR_LANGUAGES = os.getenv("OCR_LANGUAGES", "eng").strip() or "eng"
OCR_DPI = env_int("OCR_DPI", 300)

TESSERACT_CMD = env_path("TESSERACT_CMD")
POPPLER_PATH = env_path("POPPLER_PATH")


# ------------------------------------------------------------------------------
# Redis & Celery
# ------------------------------------------------------------------------------

REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1").strip()
REDIS_PORT = env_int("REDIS_PORT", 6379)
REDIS_USERNAME = os.getenv("REDIS_USERNAME", "default").strip()
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "").strip()
REDIS_USE_ACL = env_bool("REDIS_USE_ACL", False)

REDIS_CHANNEL_DB = env_int("REDIS_CHANNEL_DB", 0)
REDIS_CACHE_DB = env_int("REDIS_CACHE_DB", 1)
REDIS_CELERY_DB = env_int("REDIS_CELERY_DB", 2)
REDIS_CELERY_RESULT_DB = env_int("REDIS_CELERY_RESULT_DB", 3)

REDIS_SOCKET_CONNECT_TIMEOUT = env_float("REDIS_SOCKET_CONNECT_TIMEOUT", 3.0)
REDIS_SOCKET_TIMEOUT = env_float("REDIS_SOCKET_TIMEOUT", 3.0)
REDIS_HEALTH_CHECK_INTERVAL = env_int("REDIS_HEALTH_CHECK_INTERVAL", 30)
REDIS_RETRY_ON_TIMEOUT = env_bool("REDIS_RETRY_ON_TIMEOUT", True)
REDIS_STRICT = env_bool("REDIS_STRICT", False)
REDIS_FALLBACK_INMEMORY = env_bool("REDIS_FALLBACK_INMEMORY", True)


def build_redis_url(database: int) -> str:
    """Baut eine Redis-URL aus den bestehenden Projekt-ENV-Konventionen."""
    if REDIS_PASSWORD:
        password = quote(REDIS_PASSWORD, safe="")
        if REDIS_USE_ACL and REDIS_USERNAME:
            return f"redis://{REDIS_USERNAME}:{password}@{REDIS_HOST}:{REDIS_PORT}/{database}"
        return f"redis://:{password}@{REDIS_HOST}:{REDIS_PORT}/{database}"
    return f"redis://{REDIS_HOST}:{REDIS_PORT}/{database}"


REDIS_CELERY_URL = build_redis_url(REDIS_CELERY_DB)
REDIS_CELERY_RESULT_URL = build_redis_url(REDIS_CELERY_RESULT_DB)

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_CELERY_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_CELERY_RESULT_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = not GLOBI_USE_CELERY
CELERY_TASK_TRACK_STARTED = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_DEFAULT_QUEUE = os.getenv("CELERY_TASK_DEFAULT_QUEUE", "globi_imports").strip() or "globi_imports"


# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------

LOG_DIR = Path(env_path("DJANGO_LOG_DIR", str(BASE_DIR / "logs")))
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass

_log_file_handlers = {}
_log_file_names = {
    "django_file": "django.log",
    "errors_file": "errors.log",
    "celery_file": "celery.log",
    "imports_file": "imports.log",
}

if LOG_DIR.is_dir():
    for _handler_name, _file_name in _log_file_names.items():
        _log_file_handlers[_handler_name] = {
            "level": "WARNING" if _handler_name == "errors_file" else "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / _file_name),
            "maxBytes": env_int("DJANGO_LOG_MAX_BYTES", 5 * 1024 * 1024),
            "backupCount": env_int("DJANGO_LOG_BACKUP_COUNT", 5),
            "formatter": "verbose",
            "encoding": "utf-8",
        }

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d %(message)s",
        },
        "simple": {
            "format": "%(levelname)s %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG" if DEBUG else "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        **_log_file_handlers,
    },
    "root": {
        "handlers": ["console", *[name for name in ["django_file"] if name in _log_file_handlers]],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", *[name for name in ["django_file"] if name in _log_file_handlers]],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", *[name for name in ["errors_file"] if name in _log_file_handlers]],
            "level": "WARNING",
            "propagate": False,
        },
        "daphne": {
            "handlers": ["console", *[name for name in ["django_file"] if name in _log_file_handlers]],
            "level": "INFO",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console", *[name for name in ["celery_file"] if name in _log_file_handlers]],
            "level": "INFO",
            "propagate": False,
        },
        "apps.imports": {
            "handlers": ["console", *[name for name in ["imports_file"] if name in _log_file_handlers]],
            "level": "INFO",
            "propagate": False,
        },
    },
}


# ------------------------------------------------------------------------------
# Hinweise zu PROD
# ------------------------------------------------------------------------------
# - SECRET_KEY, Datenbankdaten und ALLOWED_HOSTS immer über .env.prod setzen.
# - DEBUG=False und HTTPS-Cookie-Flags für produktive Umgebungen aktivieren.
# - OCR bleibt lokal und nutzt keine externen Cloud-Dienste.
