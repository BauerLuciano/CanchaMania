"""Servicios de sucursales.

Punto clave de la seguridad multi-tenant: toda escritura resuelve el negocio desde
el ambito del usuario y **rechaza** cualquier `negocio_id` o `sucursal_id` ajeno,
de modo que un recurso nunca cambia de ambio por manipulacion de IDs.

`BaseScopedViewSet` invoca exactamente tres funciones de este modulo:

    valores_de_creacion(datos, usuario)              -> kwargs de serializer.save()
    valores_de_actualizacion(instancia, datos, usuario) -> kwargs de serializer.save()
    eliminar(instancia=..., usuario=...)            -> baja fisica
"""
from django.db import IntegrityError

from apps.core.exceptions import AmbitoInvalidoError, ConflictoError
from apps.core.services import generar_slug, zona_horaria_por_defecto, zona_horaria_valida
from apps.cuentas import services as cuentas_services
from apps.negocios.models import Negocio


def _zona_horaria(valor):
    if valor in (None, ""):
        return zona_horaria_por_defecto()
    if not zona_horaria_valida(valor):
        raise ConflictoError("Zona horaria IANA invalida.", codigo="ZONA_HORARIA_INVALIDA")
    return valor


def _exigir_en_ambito(instancia, usuario):
    """Verifica que la sucursal siga dentro del ambito del usuario.

    El viewset ya entrega objetos recortados; esta comprobacion es la segunda
    barrera para que ningun camino pueda saltar el filtro.
    """
    from apps.sucursales.models import Sucursal

    if not Sucursal.objects.para_usuario(usuario).filter(pk=instancia.pk).exists():
        raise AmbitoInvalidoError()
    return instancia


def _exigir_slug_libre(negocio_id, slug, excluir_id=None):
    """Comprueba la unicidad de `(negocio, slug)`.

    Vive aqui y no en el serializer porque es una regla de negocio, y porque la
    consecuencia correcta NO es un 400 de formulario: es un 409, el conflicto con
    un recurso que ya existe (SPEC §19).
    """
    from apps.sucursales.models import Sucursal

    consulta = Sucursal.objects.filter(negocio_id=negocio_id, slug=slug)
    if excluir_id is not None:
        consulta = consulta.exclude(pk=excluir_id)
    if consulta.exists():
        raise ConflictoError(
            "El negocio ya tiene una sucursal con ese identificador.",
            codigo="SLUG_EXISTENTE",
        )


def valores_de_creacion(datos, usuario):
    """Resuelve el negocio desde el ambito y prepara los valores a guardar.

    El cliente puede sugerir un `negocio`, pero si no pertenece a su ambito la
    operacion se rechaza: nunca se crea nada en un negocio ajeno.
    """
    contexto = cuentas_services.exigir_ambito(usuario)
    valores = dict(datos)

    # `serializer.save()` asigna la FK con una INSTANCIA, no con un id, asi que
    # se resuelve el negocio una vez y se vuelve a traer. El id ya quedo
    # verificado contra el ambito: `exigir_negocio` no devuelve nada sin comprobar.
    negocio_id = cuentas_services.exigir_negocio(contexto, datos.get("negocio"))
    valores["negocio"] = Negocio.objects.get(pk=negocio_id)

    nombre = valores.get("nombre") or ""
    valores["slug"] = generar_slug(valores.get("slug") or nombre)
    if not valores["slug"]:
        raise ConflictoError("El nombre no genera un slug valido.", codigo="SLUG_INVALIDO")
    _exigir_slug_libre(negocio_id, valores["slug"])

    valores["telefono"] = valores.get("telefono") or ""
    valores["direccion"] = valores.get("direccion") or ""
    valores.setdefault("activo", True)
    valores["zona_horaria"] = _zona_horaria(valores.get("zona_horaria"))
    return valores


def valores_de_actualizacion(instancia, datos, usuario):
    """Prepara los valores de una edicion.

    El negocio es INMUTABLE: mover una sucursal de negocio arrastraria sus
    membresias, canchas y caja de tenant. Si llega un `negocio` distinto al
    actual, se rechaza; si coincide, se descarta.
    """
    _exigir_en_ambito(instancia, usuario)
    contexto = cuentas_services.exigir_ambito(usuario)

    valores = dict(datos)
    negocio_enviado = valores.pop("negocio", None)
    if negocio_enviado is not None:
        negocio_id = cuentas_services.exigir_negocio(contexto, negocio_enviado)
        if negocio_id != instancia.negocio_id:
            raise AmbitoInvalidoError(
                "Una sucursal no se puede mover de negocio.", codigo="NEGOCIO_INMUTABLE"
            )

    if "slug" in valores or "nombre" in valores:
        valores["slug"] = generar_slug(valores.get("slug") or valores.get("nombre") or instancia.nombre)
        _exigir_slug_libre(instancia.negocio_id, valores["slug"], excluir_id=instancia.pk)

    if "zona_horaria" in valores:
        valores["zona_horaria"] = _zona_horaria(valores.get("zona_horaria"))
    if "telefono" in valores:
        valores["telefono"] = valores["telefono"] or ""
    if "direccion" in valores:
        valores["direccion"] = valores["direccion"] or ""
    return valores


def eliminar(*, instancia, usuario):
    """Elimina una sucursal. Solo el Dueño tiene `delete_sucursal`.

    Negocio y membresias apuntan con PROTECT: si la sede tiene personal o
    cualquier otro dato que cuelgue, se rechaza y la recomendacion es
    desactivarla (`activo=False`), no borrarla.
    """
    _exigir_en_ambito(instancia, usuario)
    sucursal_id = instancia.pk

    try:
        instancia.delete()
    except IntegrityError as exc:
        raise ConflictoError(
            "La sucursal tiene datos asociados. Considere desactivarla en lugar de eliminarla.",
            codigo="SUCURSAL_CON_DEPENDENCIAS",
        ) from exc

    cuentas_services.registrar_accion(
        actor=usuario, accion="SUCURSAL_ELIMINADA", detalle=f"sucursal_id={sucursal_id}"
    )
