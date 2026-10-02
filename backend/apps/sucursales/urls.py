"""Rutas de sucursales: `/api/sucursales/`."""
from rest_framework.routers import DefaultRouter

from apps.sucursales import views

router = DefaultRouter()
router.register("sucursales", views.SucursalViewSet, basename="sucursal")

urlpatterns = router.urls
