"""Configuracion de DESARROLLO.

- DEBUG activo.
- WhiteNoise sirve el build de Vite si existe, para probar el frontend compilado.
- El proxy de `/api` lo hace Vite (decision aprobada: sin CORS).
"""
from .base import *  # noqa: F401,F403
from .base import BASE_DIR, FRONTEND_DIST_DIR

DEBUG = True

ALLOWED_HOSTS = ["*"]

INTERNAL_IPS = ["127.0.0.1", "::1"]

# Servir el build del frontend si ya fue generado (`npm run build`).
# En desarrollo lo habitual es `npm run dev` con el proxy de Vite.
if FRONTEND_DIST_DIR.is_dir():
    WHITENOISE_ROOT = str(FRONTEND_DIST_DIR)
    WHITENOISE_INDEX_FILE = True
