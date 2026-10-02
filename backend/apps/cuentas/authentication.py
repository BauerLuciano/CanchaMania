"""Autenticacion por sesion, con el codigo de error del proyecto.

Vive en su propio modulo, y no junto a `csrf.py`, por una razon concreta: DRF
resuelve `DEFAULT_AUTHENTICATION_CLASSES` al importar sus settings, y en ese
momento `apps.core.exceptions` todavia puede estar a medio construir. Si esta
clase importara `CsrfRechazado` en el nivel superior, ese import cerraria un
ciclo. Por eso el import de `CsrfRechazado` es perezoso: ocurre en la primera
peticion, cuando todo el paquete ya esta cargado.
"""
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied


class SesionConCsrf(SessionAuthentication):
    """`SessionAuthentication` que reporta el fallo de CSRF con el codigo propio.

    DRF lanza un `PermissionDenied` generico cuando el token no cuadra, y eso
    llegaria al frontend como un 403 SIN_PERMISOS, indistinguible de "no tenes
    permiso para esto". Traducirlo mantiene una sola comprobacion de CSRF (la del
    propio DRF, sin reimplementarla) y un unico codigo para toda la API, que es
    lo que permite al frontend distinguir "recarga la pagina" de "tu sesion
    caduco" (SPEC §19).
    """

    def enforce_csrf(self, request):
        from apps.cuentas.csrf import CsrfRechazado

        try:
            super().enforce_csrf(request)
        except PermissionDenied as exc:
            raise CsrfRechazado() from exc