"""Permission classes base de CanchaMania.

La autorizacion real vive en el backend (SPEC §5). El frontend solo usa la
lista de permisos que devuelve `/api/auth/me/` para ocultar pantallas.

Dos controles independientes, ambos obligatorios en cada endpoint del panel:

1. `PermisoDeAccion`  -> el usuario tiene el permiso del modelo para la accion;
2. `ConAmbitoActivo`   -> el usuario tiene al menos una membresia activa.
"""
from rest_framework.permissions import BasePermission

from apps.core.exceptions import SinAmbitoError
from apps.core.scoping import con_ambito


class ConAmbitoActivo(BasePermission):
    """Rechaza al usuario sin ninguna membresia activa.

    Sin membresia no hay nada que ver, ni siquiera la lista vacia: evita adivinar
    la existencia de negocios ajenos.

    Levanta `SinAmbitoError` y no devuelve `False` a proposito: asi el frontend
    distingue "no tenes ningun negocio" de "no tenes permiso" (SPEC §19), que son
    pantallas y mensajes distintos.
    """

    def has_permission(self, request, view):
        if not con_ambito(request.user).tiene_ambito():
            raise SinAmbitoError()
        return True


class PermisoDeAccion(BasePermission):
    """Verifica el permiso que el viewset declara para la accion en curso.

    El viewset define `permiso_por_accion`; este permission lo consulta. Si la
    accion tiene un handler en el viewset pero no un permiso declarado, se
    rechaza: es preferible fallar cerrado.

    La excepcion son las acciones que el viewset NO implementa (por ejemplo,
    `POST` sobre un recurso de solo lectura) o que declara en
    `acciones_no_soportadas`. Ahi no hay nada que autorizar: DRF responde 405 y
    conviene que llegue ese 405 en vez de un 403, porque "no podes hacer esto" y
    "esta operacion no existe" son respuestas distintas y el frontend las trata
    distinto.
    """

    def has_permission(self, request, view):
        codigo = None
        if hasattr(view, "get_codigo_permiso"):
            codigo = view.get_codigo_permiso()
        if not codigo:
            accion = getattr(view, "action", None)
            return accion is None or accion in getattr(view, "acciones_no_soportadas", ()) or not hasattr(view, accion)

        # Import perezoso para no crear dependencia circular en el import del modulo.
        from apps.cuentas.services import usuario_tiene_permiso

        return usuario_tiene_permiso(request.user, codigo)


class EsSuperadmin(BasePermission):
    """Acceso exclusivo del Superadmin (SPEC §5, gestion por Django Admin)."""

    message = "Solo el Superadmin puede realizar esta accion."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)
