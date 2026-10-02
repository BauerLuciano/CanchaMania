"""Tests de autenticacion: CSRF, login, logout, /me y sesion.

Cubre el requisito critico de no desactivar CSRF, ni siquiera en el login.
"""
import pytest
from django.urls import reverse

from apps.cuentas.models import Membresia
from apps.core.exceptions import CSRF_INVALIDO
from apps.core.tests.factories import CONTRASENA_TEST, NegocioFactory, UsuarioFactory, dueno

pytestmark = pytest.mark.django_db


# --- Cliente HTTP con CSRF --------------------------------------------------


@pytest.fixture
def cliente():
    from rest_framework.test import APIClient

    return APIClient(enforce_csrf_checks=True)


@pytest.fixture
def usuario_dueno():
    negocio = NegocioFactory()
    usuario, membresia_dueno = dueno(negocio)
    return usuario, negocio


# --- CSRF -------------------------------------------------------------------


def test_endpoint_csrf_entrega_cookie_y_token(cliente):
    respuesta = cliente.get(reverse("auth-csrf"))

    assert respuesta.status_code == 200
    assert "csrftoken" in respuesta.cookies
    assert respuesta.data["csrf_token"]


def test_login_sin_csrf_es_rechazado(cliente, usuario_dueno):
    usuario, _ = usuario_dueno

    respuesta = cliente.post(
        reverse("auth-login"),
        {"email": usuario.email, "contrasena": CONTRASENA_TEST},
        format="json",
    )

    assert respuesta.status_code == 403
    assert respuesta.data["codigo"] == CSRF_INVALIDO
    assert "_auth_user_id" not in cliente.session


def test_logout_sin_csrf_es_rechazado(cliente, usuario_dueno):
    usuario, _ = usuario_dueno
    cliente.force_login(usuario)

    respuesta = cliente.post(reverse("auth-logout"), format="json")

    assert respuesta.status_code == 403
    assert respuesta.data["codigo"] == CSRF_INVALIDO
    assert "_auth_user_id" in cliente.session  # la sesion sigue viva


# --- Login ------------------------------------------------------------------


def _con_token_csrf(cliente):
    """Pide la cookie y el token, y devuelve las cabeceras con el token.

    CSRF exige las dos mitades: la cookie `csrftoken` Y el token en el header. Por
    eso no alcanza con el GET previo.
    """
    respuesta = cliente.get(reverse("auth-csrf"))
    return {"HTTP_X_CSRFTOKEN": respuesta.data["csrf_token"]}


def _login(cliente, email, contrasena):
    cabeceras = _con_token_csrf(cliente)
    return cliente.post(
        reverse("auth-login"),
        {"email": email, "contrasena": contrasena},
        format="json",
        **cabeceras,
    )


def test_login_exitoso_devuelve_perfil_con_permisos(cliente, usuario_dueno):
    usuario, negocio = usuario_dueno

    respuesta = _login(cliente, usuario.email, CONTRASENA_TEST)

    assert respuesta.status_code == 200
    assert respuesta.data["usuario"]["email"] == usuario.email
    assert respuesta.data["usuario"]["roles"] == ["DUENO"]
    assert respuesta.data["usuario"]["negocios"][0]["id"] == negocio.pk
    assert "negocios.view_negocio" in respuesta.data["usuario"]["permisos"]
    assert "_auth_user_id" in cliente.session


def test_login_no_revela_si_el_email_existe(cliente, usuario_dueno):
    usuario, _ = usuario_dueno

    inexistente = _login(cliente, "nadie@canchamania.test", CONTRASENA_TEST)
    contrasena_mala = _login(cliente, usuario.email, "OtraClave999")

    assert inexistente.status_code == contrasena_mala.status_code == 401
    assert inexistente.data["codigo"] == contrasena_mala.data["codigo"] == "CREDENCIALES_INVALIDAS"
    assert inexistente.data["mensaje"] == contrasena_mala.data["mensaje"]


def test_login_es_insensible_a_mayusculas(cliente, usuario_dueno):
    usuario, _ = usuario_dueno

    respuesta = _login(cliente, usuario.email.upper(), CONTRASENA_TEST)

    assert respuesta.status_code == 200


def test_login_rechaza_usuario_inactivo(cliente, usuario_dueno):
    usuario, _ = usuario_dueno
    usuario.is_active = False
    usuario.save(update_fields=["is_active"])

    respuesta = _login(cliente, usuario.email, CONTRASENA_TEST)

    assert respuesta.status_code == 401


def test_usuario_sin_membresias_no_puede_iniciar_sesion(cliente):
    usuario = UsuarioFactory()

    respuesta = _login(cliente, usuario.email, CONTRASENA_TEST)

    assert respuesta.status_code == 403
    assert respuesta.data["codigo"] == "SIN_AMBITO"
    assert "_auth_user_id" not in cliente.session


def test_login_con_credenciales_ausentes(cliente):
    cabeceras = _con_token_csrf(cliente)
    respuesta = cliente.post(reverse("auth-login"), {}, format="json", **cabeceras)

    assert respuesta.status_code == 401
    assert respuesta.data["codigo"] == "CREDENCIALES_INVALIDAS"


# --- Perfil / me ------------------------------------------------------------


def test_me_devuelve_identidad_roles_ambitos_y_permisos(cliente, usuario_dueno):
    usuario, negocio = usuario_dueno
    cliente.force_login(usuario)

    respuesta = cliente.get(reverse("auth-me"))

    assert respuesta.status_code == 200
    datos = respuesta.data
    assert datos["email"] == usuario.email
    assert datos["roles"] == ["DUENO"]
    assert datos["ambitos"] == [
        {"negocio_id": negocio.pk, "sucursal_id": None, "rol": "DUENO", "ambito": "negocio"}
    ]
    assert datos["es_superadmin"] is False
    assert "cuentas.add_membresia" in datos["permisos"]


def test_me_exige_sesion(cliente):
    respuesta = cliente.get(reverse("auth-me"))

    assert respuesta.status_code == 401
    assert respuesta.data["codigo"] == "NO_AUTENTICADO"


def test_me_omite_permisos_de_membresia_inactiva(cliente, usuario_dueno):
    usuario, negocio = usuario_dueno
    membresia = Membresia.objects.get(usuario=usuario)
    cliente.force_login(usuario)

    antes = cliente.get(reverse("auth-me")).data["permisos"]
    membresia.activa = False
    membresia.save(update_fields=["activa"])
    despues = cliente.get(reverse("auth-me")).data["permisos"]

    assert antes  # el Dueño tiene permisos
    assert despues == []


def test_catalogo_de_roles(cliente, usuario_dueno):
    cliente.force_login(usuario_dueno[0])
    respuesta = cliente.get(reverse("auth-roles"))
    roles = {r["valor"]: r for r in respuesta.data["results"]}

    assert set(roles) == {"DUENO", "ENCARGADO", "CAJERO"}
    assert roles["DUENO"]["requiere_sucursal"] is False
    assert roles["ENCARGADO"]["requiere_sucursal"] is True


# --- Logout -----------------------------------------------------------------


def test_logout_cierra_la_sesion(cliente, usuario_dueno):
    usuario, _ = usuario_dueno
    cliente.force_login(usuario)
    cabeceras = _con_token_csrf(cliente)

    respuesta = cliente.post(reverse("auth-logout"), format="json", **cabeceras)

    assert respuesta.status_code == 200
    assert "_auth_user_id" not in cliente.session
    assert cliente.get(reverse("auth-me")).status_code == 401


# --- Aislamiento de la sesion ----------------------------------------------


def test_no_se_puede_acceder_al_panel_sin_sesion(cliente, usuario_dueno):
    respuesta = cliente.get("/api/negocios/")

    assert respuesta.status_code == 401
    assert respuesta.data["codigo"] == "NO_AUTENTICADO"


def test_usuario_de_negocio_a_no_ve_negocio_b(cliente):
    negocio_a = NegocioFactory()
    negocio_b = NegocioFactory()
    usuario, _ = dueno(negocio_a)
    cliente.force_login(usuario)

    listado = cliente.get("/api/negocios/").data
    detalle = cliente.get(f"/api/negocios/{negocio_b.pk}/")

    assert [n["id"] for n in listado["results"]] == [negocio_a.pk]
    assert detalle.status_code == 404
    assert detalle.data["codigo"] == "NO_ENCONTRADO"
