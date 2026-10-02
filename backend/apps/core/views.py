"""ViewSets base con aislamiento multi-tenant obligatorio.

`BaseScopedViewSet` centraliza tres garantias para que ningun endpoint del panel
pueda olvidarlas:

1. `get_queryset()` siempre recorta por el ambito del usuario, de modo que
   `retrieve`, `update` y `destroy` operan sobre un queryset ya filtrado y un
   recurso ajeno devuelve 404 (no se confirma ni su existencia);
2. la escritura resuelve el negocio y la sucursal DESDE EL AMBITO DEL USUARIO,
   nunca desde el cuerpo de la peticion;
3. el permiso de cada accion se declara explicitamente en `permiso_por_accion`.

Este viewset no decide reglas de negocio: delega en el `services.py` de la app,
que es quien sabe que hacer (SPEC §21).
"""
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from apps.core.permissions import ConAmbitoActivo, PermisoDeAccion
from apps.core.scoping import con_ambito


class BaseScopedViewSet(viewsets.ModelViewSet):
    """CRUD REST recortado al ambito del usuario.

    Las subclases deben definir:
      * `servicios`: el modulo `services.py` de la app;
      * `permiso_por_accion`: permiso requerido por cada accion.
    """

    permission_classes = [IsAuthenticated, ConAmbitoActivo, PermisoDeAccion]

    #: Modulo `services.py` de la app. Lo inyecta cada viewset concreto.
    servicios = None

    #: Permiso requerido por accion, en formato "app_label.codename".
    permiso_por_accion: dict[str, str] = {}

    #: Permiso usado para acciones no mapeadas explicitamente.
    permiso_por_defecto: str | None = None

    #: Acciones que el recurso no admite en esta etapa, aunque el viewset las
    #: declare para poder responder con su propio mensaje (405 METHOD_NOT_ALLOWED).
    #: `PermisoDeAccion` las deja pasar: no hay nada que autorizar, la peticion se
    #: va a rechazar igual. Ejemplo: los usuarios no se borran, se desactivan.
    acciones_no_soportadas: tuple[str, ...] = ()

    def get_codigo_permiso(self) -> str | None:
        accion = getattr(self, "action", None)
        return self.permiso_por_accion.get(accion, self.permiso_por_defecto)

    # -- Aislamiento --------------------------------------------------------

    def get_queryset(self):
        base = self.queryset.all() if self.queryset is not None else self.model.objects.all()
        return base.para_usuario(self.request.user)

    def get_serializer_context(self):
        contexto = super().get_serializer_context()
        contexto["usuario"] = self.request.user
        contexto["contexto_ambito"] = con_ambito(self.request.user).contexto
        return contexto

    # -- Escrituras: el servicio resuelve el ambito, la vista solo orquesta --

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valores = self.servicios.valores_de_creacion(
            datos=dict(serializer.validated_data), usuario=request.user
        )
        instancia = serializer.save(**valores)
        return Response(self.get_serializer(instancia).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        valores = self.servicios.valores_de_actualizacion(
            instancia=serializer.instance,
            datos=dict(serializer.validated_data),
            usuario=self.request.user,
        )
        serializer.save(**valores)

    def perform_destroy(self, instance):
        self.servicios.eliminar(instancia=instance, usuario=self.request.user)
