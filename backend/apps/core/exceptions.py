"""Formato de error uniforme de la API (SPEC §19).

Toda respuesta de error de CanchaMania tiene esta forma:

    {
      "codigo": "CODIGO_ESTABLE",
      "mensaje": "Texto legible para la persona usuaria",
      "detalles": {...}   # opcional: errores por campo u operacion
    }

El frontend muestra `mensaje` y nunca necesita parsear texto libre.
"""
from __future__ import annotations

import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


# --- Codigos estables -------------------------------------------------------
# Autenticacion / sesion
NO_AUTENTICADO = "NO_AUTENTICADO"
CREDENCIALES_INVALIDAS = "CREDENCIALES_INVALIDAS"
CSRF_INVALIDO = "CSRF_INVALIDO"
SESION_EXPIRADA = "SESION_EXPIRADA"

# Autorizacion
SIN_PERMISOS = "SIN_PERMISOS"
SIN_AMBITO = "SIN_AMBITO"
AMBITO_INVALIDO = "AMBITO_INVALIDO"

# Validacion / dominio
VALIDACION_INVALIDA = "VALIDACION_INVALIDA"
CONFLICTO = "CONFLICTO"
NO_ENCONTRADO = "NO_ENCONTRADO"
METODO_NO_PERMITIDO = "METODO_NO_PERMITIDO"

# Generico
ERROR_INTERNO = "ERROR_INTERNO"


class ErrorCanchaMania(APIException):
    """Excepcion de dominio con codigo y mensaje estables.

    `detalle` es el mensaje por defecto de la subclase; `mensaje` es el que se
    devuelve. `APIException.detail` solo existe despues de `super().__init__()`,
    por eso el mensaje por defecto se lee de `detalle` y no de `self.detail`.
    """

    status_code = status.HTTP_400_BAD_REQUEST
    codigo = "ERROR"
    detalle = "Se produjo un error en la solicitud."

    def __init__(self, mensaje=None, codigo=None, status_code=None, detalles=None):
        self.codigo = codigo or self.codigo
        self.mensaje = mensaje or self.detalle
        self.detalles = detalles
        if status_code is not None:
            self.status_code = status_code
        super().__init__(detail=self.mensaje)

    def como_dict(self):
        cuerpo = {"codigo": self.codigo, "mensaje": self.mensaje}
        if self.detalles:
            cuerpo["detalles"] = self.detalles
        return cuerpo


class SinAmbitoError(ErrorCanchaMania):
    """El usuario no tiene ninguna membresia activa: no hay nada que listar ni tocar."""

    status_code = status.HTTP_403_FORBIDDEN
    codigo = SIN_AMBITO
    detalle = "El usuario no tiene membresias activas en ningun negocio."


class AmbitoInvalidoError(ErrorCanchaMania):
    """El recurso solicitado o enviado queda fuera del ambito del usuario."""

    status_code = status.HTTP_403_FORBIDDEN
    codigo = AMBITO_INVALIDO
    detalle = "El recurso solicitado no pertenece a su ambito."


class ConflictoError(ErrorCanchaMania):
    status_code = status.HTTP_409_CONFLICT
    codigo = CONFLICTO
    detalle = "La operacion entra en conflicto con el estado actual del recurso."


class CredencialesInvalidasError(ErrorCanchaMania):
    status_code = status.HTTP_401_UNAUTHORIZED
    codigo = CREDENCIALES_INVALIDAS
    detalle = "Email o contrasena incorrectos."


def construir_error(codigo, mensaje, http_status, detalles=None) -> Response:
    cuerpo = {"codigo": codigo, "mensaje": mensaje}
    if detalles:
        cuerpo["detalles"] = detalles
    return Response(cuerpo, status=http_status)


def _codigo_por_http(http_status) -> str:
    return {
        400: VALIDACION_INVALIDA,
        401: NO_AUTENTICADO,
        403: SIN_PERMISOS,
        404: NO_ENCONTRADO,
        405: METODO_NO_PERMITIDO,
        409: CONFLICTO,
        415: VALIDACION_INVALIDA,
        429: "DEMASIADOS_INTENTOS",
    }.get(http_status, ERROR_INTERNO)


def _mensaje_por_http(http_status) -> str:
    return {
        400: "Los datos enviados no son validos.",
        401: "Debe iniciar sesion para continuar.",
        403: "No tiene permisos para realizar esta accion.",
        404: "El recurso solicitado no existe o no pertenece a su ambito.",
        405: "Metodo no permitido.",
        409: "La operacion entra en conflicto con el estado actual.",
        429: "Demasiados intentos. Intente nuevamente en unos instantes.",
    }.get(http_status, "Ocurrio un error inesperado.")


def _validacion_a_detalles(detalle) -> dict | None:
    """Convierte la estructura de errores de DRF en un diccionario por campo."""
    if isinstance(detalle, dict):
        return {str(k): _normalizar_valor(v) for k, v in detalle.items()}
    if isinstance(detalle, list):
        # NonFieldError
        return {"no_campo": [_normalizar_valor(v) for v in detalle]}
    return {"no_campo": _normalizar_valor(detalle)}


def _normalizar_valor(valor):
    if isinstance(valor, (list, tuple)):
        return " ".join(str(v) for v in valor)
    if isinstance(valor, dict):
        return "; ".join(str(v) for v in valor.values())
    return str(valor)


def _detalles_de_django(exc: DjangoValidationError):
    """Convierte un `ValidationError` de Django en un diccionario por campo.

    Es lo que permite que los mensajes del `clean()` de los modelos lleguen al
    frontend en `detalles` en lugar de perderse.
    """
    if hasattr(exc, "message_dict"):
        return {campo: _normalizar_valor(mensajes) for campo, mensajes in exc.message_dict.items()}
    if hasattr(exc, "messages"):
        return {"no_campo": " ".join(exc.messages)}
    return None


def handler_de_excepciones(exc, contexto):
    """Exception handler global de DRF: garantiza el formato uniforme."""
    if isinstance(exc, ErrorCanchaMania):
        return Response(exc.como_dict(), status=exc.status_code)

    # DRF degrada `NotAuthenticated` a 403 cuando la autenticacion no define
    # cabecera `WWW-Authenticate` (caso de la sesion con cookie). Se restaura el
    # 401 para que el frontend distinga "sesion expirada" de "sin permiso": los
    # dos casos son de lo mas distintos y no se pueden tratar igual.
    if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        return construir_error(
            NO_AUTENTICADO, _mensaje_por_http(401), status.HTTP_401_UNAUTHORIZED
        )

    if isinstance(exc, DjangoValidationError):
        return construir_error(
            VALIDACION_INVALIDA,
            "Los datos enviados no son validos.",
            400,
            _detalles_de_django(exc),
        )

    if isinstance(exc, DjangoPermissionDenied):
        return construir_error(SIN_PERMISOS, _mensaje_por_http(403), 403)

    if isinstance(exc, ValidationError):
        return construir_error(
            VALIDACION_INVALIDA,
            "Los datos enviados no son validos.",
            400,
            _validacion_a_detalles(exc.detail),
        )

    respuesta = drf_exception_handler(exc, contexto)
    if respuesta is not None:
        codigo = getattr(exc, "codigo", None) or _codigo_por_http(respuesta.status_code)
        detalles = _validacion_a_detalles(respuesta.data)
        cuerpo = {
            "codigo": codigo,
            "mensaje": _mensaje_por_http(respuesta.status_code),
        }
        if detalles and any(k != "detail" for k in detalles):
            cuerpo["detalles"] = detalles
        elif isinstance(respuesta.data, dict) and "detail" in respuesta.data:
            cuerpo["mensaje"] = str(respuesta.data["detail"])
        return Response(cuerpo, status=respuesta.status_code)

    # Cualquier otra excepcion es un error del servidor: se registra completa
    # y se responde sin filtrar detalles internos.
    logger.exception("Error no controlado en la API", exc_info=exc)
    return construir_error(ERROR_INTERNO, _mensaje_por_http(500), 500)


def error_de_integridad(
    exc: IntegrityError, codigo=CONFLICTO, mensaje=None
) -> ConflictoError:
    """Convierte un error de integridad de PostgreSQL en un 409 con codigo estable.

    Uso:  `raise error_de_integridad(exc, mensaje="El slug ya existe.") from exc`
    """
    return ConflictoError(
        mensaje or "La operacion entra en conflicto con datos existentes.", codigo=codigo
    )
