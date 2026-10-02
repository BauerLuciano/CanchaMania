"""Servicios de negocios.

En la Etapa 1 el recurso `Negocio` es de **solo lectura** desde el panel:

* el alta de un negocio no tiene flujo definido en el SPEC (ni onboarding, ni
  suscripcion: §26 la deja pendiente), asi que se hace por Django Admin o por el
  management command `crear_negocio`, no inventando una API;
* `activo` es una bandera tecnica, no una regla comercial.
"""
from django.db import IntegrityError, transaction

from apps.core.exceptions import ConflictoError
from apps.core.services import generar_slug


def normalizar_slug(nombre: str, slug: str | None = None) -> str:
    """Slug explicito si viene, derivado del nombre si no."""
    return generar_slug(slug or nombre)


@transaction.atomic
def crear_negocio(*, nombre, slug=None, activo=True):
    """Alta de negocio. Solo Superadmin / Django Admin / management command."""
    from apps.negocios.models import Negocio

    slug = normalizar_slug(nombre, slug)
    if not slug:
        raise ConflictoError("El nombre no genera un slug valido.", codigo="SLUG_INVALIDO")
    try:
        return Negocio.objects.create(nombre=nombre, slug=slug, activo=activo)
    except IntegrityError as exc:
        raise ConflictoError("Ya existe un negocio con ese slug.", codigo="SLUG_EXISTENTE") from exc


# --- Contrato que exige BaseScopedViewSet -----------------------------------
# El viewset de negocios es de solo lectura, asi que no usa escrituras. Se
# mantienen las funciones para que la firma del viewset base no quede implicita.


def valores_de_creacion(datos, usuario):
    """No se permite crear negocios desde el panel en la Etapa 1."""
    from rest_framework.exceptions import PermissionDenied

    raise PermissionDenied(
        "El alta de negocios se realiza por administracion o con `manage.py crear_negocio`."
    )


def valores_de_actualizacion(instancia, datos, usuario):
    return {}


def eliminar(instancia, usuario):
    from rest_framework.exceptions import MethodNotAllowed

    raise MethodNotAllowed("DELETE", detail="El borrado de negocios no esta habilitado.")
