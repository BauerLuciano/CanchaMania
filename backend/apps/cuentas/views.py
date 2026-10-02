"""Vistas de cuentas: autenticacion, perfil, usuarios y membresias.

Todas las escrituras exigen CSRF: `CsrfViewMiddleware` + `SessionAuthentication` de DRF
para las ya autenticadas y comprobacion explicita para el login. No hay JWT.
"""
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import (
    SIN_AMBITO,
    AmbitoInvalidoError,
    construir_error,
)
from apps.core.scoping import con_ambito
from apps.core.views import BaseScopedViewSet
from apps.cuentas import services
from apps.cuentas.csrf import exigir_csrf
from apps.cuentas.models import Membresia, Usuario
from apps.cuentas.roles import roles_disponibles
from apps.cuentas.serializers import (
    MembresiaCrearSerializer,
    MembresiaSerializer,
    UsuarioActualizacionSerializer,
    UsuarioCrearSerializer,
    UsuarioSerializer,
)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """Entrega la cookie CSRF. El frontend la lee antes de cualquier POST."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"codigo": "OK", "csrf_token": get_token(request)})


class LoginView(APIView):
    """Login interno por email y contrasena, con sesion Django.

    El CSRF se exige tambien aca: sin el, un sitio externo podria iniciar sesion
    en el navegador de la persona con su cuenta.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        exigir_csrf(request)

        email = request.data.get("email", "")
        contrasena = request.data.get("contrasena", request.data.get("password", ""))
        usuario = services.iniciar_sesion(email=email, contrasena=contrasena)

        # Sin membresias activas no hay panel: se rechaza antes de abrir sesion para
        # no dejar una sesion inutilizable en el navegador.
        if not con_ambito(usuario).tiene_ambito() and not usuario.is_superuser:
            return construir_error(
                SIN_AMBITO,
                "El usuario no tiene membresias activas en ningun negocio.",
                status.HTTP_403_FORBIDDEN,
            )

        # Backend explicito: rota la clave de sesion contra fijacion de sesion.
        django_login(request, usuario, backend="django.contrib.auth.backends.ModelBackend")
        return Response({"codigo": "OK", "usuario": services.perfil_de(usuario)})


class LogoutView(APIView):
    """Cierra la sesion. CSRF obligatorio."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        exigir_csrf(request)
        django_logout(request)
        return Response({"codigo": "OK", "mensaje": "Sesion cerrada."})


class PerfilView(APIView):
    """`GET /api/auth/me/`: identidad, roles, ambitos y permisos calculados."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(services.perfil_de(request.user))


class CatalogoRolesView(APIView):
    """Catalogo tecnico de roles, para que el frontend no los invente."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"results": roles_disponibles()})


class UsuarioViewSet(BaseScopedViewSet):
    """Usuarios visibles dentro del ambito del operador.

    El rol no se edita aca: vive en la Membresia, que es un recurso aparte. La
    baja es logica (`POST .../desactivar/`), nunca un borrado.
    """

    serializer_class = UsuarioSerializer
    servicios = services
    permiso_por_accion = {
        "list": "cuentas.view_usuario",
        "retrieve": "cuentas.view_usuario",
        "create": "cuentas.add_usuario",
        "update": "cuentas.change_usuario",
        "partial_update": "cuentas.change_usuario",
        "desactivar": "cuentas.change_usuario",
    }
    # `destroy` esta implementado solo para responder con el mensaje que dice que
    # hay que usar `desactivar`: no se autoriza, no se ejecuta.
    acciones_no_soportadas = ("destroy",)

    def get_queryset(self):
        """Solo usuarios con membresias dentro del ambito del operador."""
        ids = (
            Membresia.objects.para_usuario(self.request.user)
            .values_list("usuario_id", flat=True)
            .distinct()
        )
        return Usuario.objects.filter(pk__in=list(ids)).order_by("email")

    def get_serializer_class(self):
        if self.action == "create":
            return UsuarioCrearSerializer
        if self.action in {"update", "partial_update"}:
            return UsuarioActualizacionSerializer
        return UsuarioSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        usuario = services.crear_usuario(**serializer.validated_data, usuario_creador=request.user)
        return Response(UsuarioSerializer(usuario).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """Edita solo los campos que expone `UsuarioActualizacionSerializer`.

        Se delega en el serializer y no en un `setattr` manual sobre
        `validated_data`: los nombres de la API (`nombre`, `apellido`) no son
        columnas del modelo, y el `source` del campo es quien sabe a que atributo
        corresponde cada uno.
        """
        instancia = self.get_object()
        serializer = self.get_serializer(
            instancia, data=request.data, partial=kwargs.pop("partial", False)
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UsuarioSerializer(instancia).data)

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed(
            request.method,
            detail="Los usuarios no se borran. Use POST /api/usuarios/<id>/desactivar/.",
        )

    @action(detail=True, methods=["post"], url_path="desactivar")
    def desactivar(self, request, pk=None):
        """Baja logica (SPEC §20 Usuarios: baja/desactivación)."""
        usuario = services.desactivar_usuario(self.get_object(), request.user)
        return Response(UsuarioSerializer(usuario).data)


class MembresiaViewSet(BaseScopedViewSet):
    """Membresias visibles dentro del ambito del operador."""

    serializer_class = MembresiaSerializer
    servicios = services
    permiso_por_accion = {
        "list": "cuentas.view_membresia",
        "retrieve": "cuentas.view_membresia",
        "create": "cuentas.add_membresia",
        "destroy": "cuentas.change_membresia",
    }

    def get_queryset(self):
        """Membresias del ambito del operador, incluida la suya propia.

        Se incluye a si mismo porque el listado responde "quien tiene acceso en mi
        ambito", y el operador tiene acceso. La proteccion contra la
        auto-desactivacion va en el servicio (`desactivar_membresia`), que es
        donde se puede comprobar sin depender de lo que se muestra.
        """
        return Membresia.objects.para_usuario(self.request.user).select_related(
            "usuario", "negocio", "sucursal"
        )

    def get_serializer_class(self):
        if self.action == "create":
            return MembresiaCrearSerializer
        return MembresiaSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = dict(serializer.validated_data)

        usuario = self._usuario_en_ambito(datos.pop("usuario"))
        membresia = services.crear_membresia(
            usuario=usuario,
            rol=datos["rol"],
            usuario_creador=request.user,
            # El serializer entrega las INSTANCIAS ya recortadas al ambito; el
            # servicio las vuelve a pasar por `exigir_negocio` / `exigir_sucursal`.
            negocio_id=datos.get("negocio"),
            sucursal_id=datos.get("sucursal"),
        )
        return Response(MembresiaSerializer(membresia).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        """Desactiva la membresia. No se borra: queda el rastro (SPEC §17)."""
        services.desactivar_membresia(self.get_object(), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _usuario_en_ambito(self, usuario_id):
        """Resuelve el usuario destino exigiendo que sea alcanzable para el operador.

        La regla vive en `services.py` (`exigir_usuario_alcanzable`): aqui solo se
        delega. No se hace `Usuario.objects.get(pk=...)` a secas, porque conocer un
        ID no habilita a tocar a nadie de otro negocio.
        """
        return services.exigir_usuario_alcanzable(usuario_id, self.request.user)
