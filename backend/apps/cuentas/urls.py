"""Rutas del panel de cuentas: `/api/usuarios/`, `/api/membresias/`."""
from rest_framework.routers import DefaultRouter

from apps.cuentas import views

router = DefaultRouter()
router.register("usuarios", views.UsuarioViewSet, basename="usuario")
router.register("membresias", views.MembresiaViewSet, basename="membresia")

urlpatterns = router.urls
