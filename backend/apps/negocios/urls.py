"""Rutas de negocios: `/api/negocios/`."""
from rest_framework.routers import DefaultRouter

from apps.negocios import views

router = DefaultRouter()
router.register("negocios", views.NegocioViewSet, basename="negocio")

urlpatterns = router.urls
