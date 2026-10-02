"""Vistas de sucursales.

CRUD completo, siempre recortado al ambito del usuario. Los permisos por accion
son los `model permissions` de Django declarados explicitamente: el backend decide,
nunca el frontend (SPEC §5).
"""
from apps.core.views import BaseScopedViewSet
from apps.sucursales import services
from apps.sucursales.models import Sucursal
from apps.sucursales.serializers import SucursalSerializer


class SucursalViewSet(BaseScopedViewSet):
    """Listado, detalle, alta, edicion y baja de sucursales del ambito."""

    queryset = Sucursal.objects.select_related("negocio").all()
    serializer_class = SucursalSerializer
    servicios = services
    permiso_por_accion = {
        "list": "sucursales.view_sucursal",
        "retrieve": "sucursales.view_sucursal",
        "create": "sucursales.add_sucursal",
        "update": "sucursales.change_sucursal",
        "partial_update": "sucursales.change_sucursal",
        "destroy": "sucursales.delete_sucursal",
    }
