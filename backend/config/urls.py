"""URLs raiz del proyecto CanchaMania.

Todas las rutas de la API viven bajo el prefijo /api/ (SPEC §19).
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.cuentas.urls_auth")),
    path("api/", include("apps.cuentas.urls")),
    path("api/", include("apps.negocios.urls")),
    path("api/", include("apps.sucursales.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Frontend compilado (SPA). Solo tiene efecto cuando existe `frontend/dist`,
# que WhiteNoise sirve desde WHITENOISE_ROOT en cada entorno.
urlpatterns += [
    re_path(
        r"^(?!api/|admin/|static/|media/).*$",
        TemplateView.as_view(template_name="index.html"),
        name="frontend",
    ),
]
