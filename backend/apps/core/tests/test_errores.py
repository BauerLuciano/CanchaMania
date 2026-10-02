"""Tests del formato de error uniforme (SPEC §19).

Toda respuesta de error debe traer `codigo` y `mensaje`, y el frontend no debe
tener que adivinar el tipo de error a partir del texto.
"""
import pytest

from apps.core.exceptions import (
    CSRF_INVALIDO,
    NO_AUTENTICADO,
    NO_ENCONTRADO,
    SIN_AMBITO,
    SIN_PERMISOS,
    VALIDACION_INVALIDA,
)
from apps.core.tests.factories import NegocioFactory, SucursalFactory, UsuarioFactory, dueno

pytestmark = pytest.mark.django_db


@pytest.fixture
def cliente():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def escenario():
    negocio = NegocioFactory()
    sucursal = SucursalFactory(negocio=negocio)
    usuario, _ = dueno(negocio)
    return usuario, negocio, sucursal


def _tiene_forma_uniforme(respuesta):
    return set(respuesta.data) >= {"codigo", "mensaje"}


def test_error_por_sesion_ausente(cliente):
    respuesta = cliente.get("/api/sucursales/")

    assert respuesta.status_code == 401
    assert _tiene_forma_uniforme(respuesta)
    assert respuesta.data["codigo"] == NO_AUTENTICADO


def test_error_por_recurso_inexistente_o_ajeno(cliente, escenario):
    usuario, _, _ = escenario
    cliente.force_login(usuario)

    respuesta = cliente.get("/api/sucursales/999999/")

    assert respuesta.status_code == 404
    assert _tiene_forma_uniforme(respuesta)
    assert respuesta.data["codigo"] == NO_ENCONTRADO
    # No se distingue "no existe" de "no es tuyo": no se filtra informacion.
    assert "999999" not in respuesta.data["mensaje"]


def test_error_de_validacion_incluye_detalles_por_campo(cliente, escenario):
    usuario, _, _ = escenario
    cliente.force_login(usuario)

    respuesta = cliente.post("/api/sucursales/", {"telefono": "123"}, format="json")

    assert respuesta.status_code == 400
    assert respuesta.data["codigo"] == VALIDACION_INVALIDA
    assert "nombre" in respuesta.data["detalles"]


def test_error_de_csrf(cliente):
    from rest_framework.test import APIClient

    csrf_client = APIClient(enforce_csrf_checks=True)
    respuesta = csrf_client.post(
        "/api/auth/login/", {"email": "x@y.test", "contrasena": "Clave12345"}, format="json"
    )

    assert respuesta.status_code == 403
    assert respuesta.data["codigo"] == CSRF_INVALIDO


def test_error_sin_ambito(cliente):
    cliente.force_login(UsuarioFactory())

    respuesta = cliente.get("/api/negocios/")

    assert respuesta.status_code == 403
    assert respuesta.data["codigo"] == SIN_AMBITO


def test_error_de_permisos(cliente):
    from apps.core.tests.factories import cajero

    negocio = NegocioFactory()
    sucursal = SucursalFactory(negocio=negocio)
    usuario, _ = cajero(negocio, sucursal)
    cliente.force_login(usuario)

    respuesta = cliente.post("/api/sucursales/", {"nombre": "No"}, format="json")

    assert respuesta.status_code == 403
    assert respuesta.data["codigo"] == SIN_PERMISOS


def test_metodo_no_permitido(cliente, escenario):
    usuario, negocio, _ = escenario
    cliente.force_login(usuario)

    respuesta = cliente.post("/api/negocios/", {"nombre": "Inventado"}, format="json")

    assert respuesta.status_code == 405
    assert _tiene_forma_uniforme(respuesta)
    assert respuesta.data["codigo"] == "METODO_NO_PERMITIDO"


def test_ruta_inexistente_devuelve_404_de_django(cliente, escenario):
    cliente.force_login(escenario[0])

    respuesta = cliente.get("/api/no-existe/")

    assert respuesta.status_code == 404
