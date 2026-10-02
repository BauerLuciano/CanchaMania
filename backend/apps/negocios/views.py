"""Vistas de negocios: solo lectura, siempre recortadas al ambito del usuario."""
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.core.permissions import ConAmbitoActivo, PermisoDeAccion
from apps.negocios import services
from apps.negocios.models import Negocio
from apps.negocios.serializers import NegocioSerializer


class NegocioViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Listado y detalle de negocios del ambito del usuario.

    Sin escritura en la Etapa 1: el alta de un negocio no tiene flujo definido en
    el SPEC y la suscripcion comercial esta pendiente (§26).
    """

    queryset = Negocio.objects.all()
    serializer_class = NegocioSerializer
    permission_classes = [IsAuthenticated, ConAmbitoActivo, PermisoDeAccion]
    permiso_por_accion = {
        "list": "negocios.view_negocio",
        "retrieve": "negocios.view_negocio",
    }
    servicios = services

    def get_codigo_permiso(self):
        return self.permiso_por_accion.get(getattr(self, "action", None))

    def get_queryset(self):
        return super().get_queryset().para_usuario(self.request.user)
