"""Comprobacion explicita de CSRF para las vistas de API de DRF.

`CsrfViewMiddleware` de Django no se aplica a las vistas de DRF (son `csrf_exempt`),
pero la sesion si lo exige: por eso el login, que todavia no tiene sesion, necesita
la comprobacion a mano. Se reutiliza el middleware real de Django en lugar de
reimplementar la comparacion del token, para no terminar con dos reglas distintas.

No se desactiva CSRF en ningun punto del proyecto.
"""
from django.middleware.csrf import CsrfViewMiddleware

from apps.core.exceptions import CSRF_INVALIDO, ErrorCanchaMania


class CsrfRechazado(ErrorCanchaMania):
    """Token CSRF ausente, invalido o con formato incorrecto."""

    status_code = 403
    codigo = CSRF_INVALIDO
    detalle = "Falta el token CSRF o es invalido. Recargue la pagina e intente de nuevo."


class _ComprobacionCsrf(CsrfViewMiddleware):
    """CsrfViewMiddleware que devuelve el motivo del rechazo en vez de lanzar excepcion."""

    def _reject(self, request, reason):
        return reason


def exigir_csrf(request):
    """Verifica el token CSRF de la peticion o lanza `CsrfRechazado` (403).

    Acepta el token en el header `X-CSRFToken` (lo que envia el frontend) o en el
    campo `csrfmiddlewaretoken` (formularios HTML). Los metodos seguros no se
    verifican, que es el comportamiento estandar del middleware.
    """
    comprobacion = _ComprobacionCsrf(lambda req: None)
    try:
        comprobacion.process_request(request)
        motivo = comprobacion.process_view(request, None, (), {})
    except Exception as exc:  # token con formato invalido
        raise CsrfRechazado() from exc
    if motivo:
        raise CsrfRechazado()
