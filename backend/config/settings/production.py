"""Configuracion de PRODUCCION.

- DEBUG siempre False.
- WhiteNoise sirve el frontend compilado (`npm run build`) bajo el mismo origen
  que la API (decision aprobada: un solo dominio, sin CORS).
- Cookies de sesion seguras y SameSite laxo para permitir el mismo origen.
"""
import os

from .base import *  # noqa: F401,F403
from .base import BASE_DIR, FRONTEND_DIST_DIR  # noqa: E402

DEBUG = False

if not os.environ.get("DJANGO_SECRET_KEY"):
    raise RuntimeError("DJANGO_SECRET_KEY es obligatoria en produccion.")

# Cabeceras de seguridad basicas (SPEC §22).
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "0"))
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# Un unico origen: Django sirve el build de Vite.
WHITENOISE_ROOT = str(FRONTEND_DIST_DIR)
WHITENOISE_INDEX_FILE = True
WHITENOISE_MAX_AGE = 31536000

CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]
