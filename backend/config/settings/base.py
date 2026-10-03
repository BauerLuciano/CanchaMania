"""Configuracion comun a todos los entornos.

Lee las variables de entorno desde el archivo `.env` de la raiz de `backend/`
mediante python-dotenv. Ningun valor sensible esta escrito en el codigo.
"""
from pathlib import Path

from dotenv import load_dotenv
import os

# .../backend  (este archivo vive en backend/config/settings/)
BASE_DIR = Path(__file__).resolve().parents[2]

# El .env puede estar ausente (por ejemplo en produccion, donde las variables
# llegan por entorno). En ese caso se usan solamente las variables reales.
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)


def _bool(nombre, por_defecto=False):
    valor = os.environ.get(nombre)
    if valor is None:
        return por_defecto
    return valor.strip().lower() in {"1", "true", "yes", "si", "on"}


def _lista(nombre, por_defecto=()):
    valor = os.environ.get(nombre, "")
    partes = [p.strip() for p in valor.split(",")]
    return [p for p in partes if p] or list(por_defecto)


# --- Identidad del proyecto (identificadores tecnicos en ASCII, sin acentos) ---
PROJECT_NAME = "CanchaMania"
PROJECT_DESCRIPTION = "Sistema de gestion para complejos de canchas"

# --- Seguridad ---
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
DEBUG = _bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = _lista("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"])

# --- Aplicaciones ---
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Terceros
    "rest_framework",
    # CanchaMania
    "apps.core",
    "apps.cuentas",
    "apps.negocios",
    "apps.sucursales",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

# Frontend compilado que Django sirve en produccion (decision aprobada).
# Se resuelve aqui, antes de TEMPLATES, porque el catch-all de la SPA de
# `config.urls` renderiza `index.html` con `TemplateView` y ese archivo vive en
# el build de Vite. Sin sumarlo a `DIRS` ninguna ruta profunda encontraba la
# plantilla y devolvia 500 con TemplateDoesNotExist.
FRONTEND_DIST_DIR = (BASE_DIR / os.environ.get("FRONTEND_DIST_DIR", "../frontend/dist")).resolve()

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates", FRONTEND_DIST_DIR],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --- Base de datos: PostgreSQL, nunca SQLite (decision aprobada) ---
DATABASES = {
    "default": {
        "ENGINE": os.environ.get("DATABASE_ENGINE", "django.db.backends.postgresql"),
        "NAME": os.environ.get("DATABASE_NAME", "canchamania"),
        "USER": os.environ.get("DATABASE_USER", "postgres"),
        "PASSWORD": os.environ.get("DATABASE_PASSWORD", ""),
        "HOST": os.environ.get("DATABASE_HOST", "localhost"),
        "PORT": os.environ.get("DATABASE_PORT", "5432"),
        "CONN_MAX_AGE": int(os.environ.get("DATABASE_CONN_MAX_AGE", "60")),
        "ATOMIC_REQUESTS": False,
        "TEST": {"NAME": os.environ.get("DATABASE_TEST_NAME", "test_canchamania")},
    }
}

# Autenticacion: sesion Django + cookie + CSRF (SPEC §3). Nada de JWT.
AUTH_USER_MODEL = "cuentas.Usuario"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"

# --- Internacionalizacion (SPEC §1: Argentina, ARS, es-AR) ---
LANGUAGE_CODE = "es-ar"
DEFAULT_TIME_ZONE = os.environ.get("DEFAULT_TIME_ZONE", "America/Argentina/Buenos_Aires")
TIME_ZONE = DEFAULT_TIME_ZONE
USE_I18N = True
USE_TZ = True

# --- Archivos estaticos ---
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
WHITENOISE_AUTOREFRESH = DEBUG

# --- Django REST Framework ---
REST_FRAMEWORK = {
    # Sesion Django. CsrfViewMiddleware + SessionAuthentication protegen cada escritura.
    # La autenticacion es la del proyecto para que el fallo de CSRF salga con el
    # codigo CSRF_INVALIDO y no como un 403 genérico (ver apps.cuentas.csrf).
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.cuentas.authentication.SesionConCsrf",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.PaginacionPorDefecto",
    "PAGE_SIZE": 50,
    "EXCEPTION_HANDLER": "apps.core.exceptions.handler_de_excepciones",
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

# --- Django Admin (Superadmin, SPEC §5) ---
ADMIN_SITE_HEADER = "CanchaMania - Administracion"
ADMIN_SITE_TITLE = "CanchaMania"
ADMIN_INDEX_TITLE = "Administracion global"

# --- Limites de tasa (SPEC §19 / §22) ---
# Los endpoints publicos los ajustaran en su etapa. Los del panel quedan
# protegidos por ambito + permiso, que es la restriccion real.
DJANGO_RATE_LIMIT = os.environ.get("DJANGO_RATE_LIMIT", "600/min")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{levelname}] {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
