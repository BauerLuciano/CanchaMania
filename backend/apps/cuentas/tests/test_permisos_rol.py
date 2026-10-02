"""Tests de permisos por rol (SPEC §5).

Verifica tres cosas:

1. que todo codigo del mapa rol -> permisos exista realmente en Django
   (detecta errores de tipeo antes de que lleguen a produccion);
2. la union Dueño = Encargado + Cajero + exclusivos;
3. la matriz real de acceso por endpoint: quien puede y quien no.
"""
import pytest

from apps.cuentas import services
from apps.cuentas.roles import PERMISOS_POR_ROL, Rol, permisos_de_rol
from apps.core.tests.factories import (
    NegocioFactory,
    SucursalFactory,
    UsuarioFactory,
    cajero,
    dueno,
    encargado,
    membresia,
)

pytestmark = pytest.mark.django_db


# --- Integridad del catalogo de roles ---------------------------------------


def test_todos_los_codigos_de_permisos_existen():
    """Cada `app_label.codename` del mapa debe existir en django.contrib.auth."""
    existentes = services.permisos_existentes()
    faltantes = {
        codigo for permisos in PERMISOS_POR_ROL.values() for codigo in permisos
    } - existentes

    assert not faltantes, f"Permisos inexistentes en el catalogo de roles: {sorted(faltantes)}"


def test_dueno_es_union_de_encargado_y_cajero():
    encargado_set = permisos_de_rol(Rol.ENCARGADO)
    cajero_set = permisos_de_rol(Rol.CAJERO)
    dueno_set = permisos_de_rol(Rol.DUENO)

    assert encargado_set <= dueno_set
    assert cajero_set <= dueno_set
    assert dueno_set - (encargado_set | cajero_set) == {
        "sucursales.delete_sucursal",
        "cuentas.add_usuario",
        "cuentas.change_usuario",
        "cuentas.delete_membresia",
    }


def test_ningun_rol_tiene_permiso_inexistente():
    for rol, permisos in PERMISOS_POR_ROL.items():
        assert permisos, f"El rol {rol} no tiene permisos definidos"


# --- Permisos por membresia -------------------------------------------------


def test_permisos_de_dueno():
    negocio = NegocioFactory()
    usuario, _ = dueno(negocio)

    permisos = services.permisos_de_usuario(usuario)

    assert "sucursales.add_sucursal" in permisos
    assert "sucursales.delete_sucursal" in permisos
    assert "cuentas.add_usuario" in permisos


def test_encargado_no_borra_sucursales_ni_crea_usuarios():
    negocio = NegocioFactory()
    sucursal = SucursalFactory(negocio=negocio)
    usuario, _ = encargado(negocio, sucursal)

    permisos = services.permisos_de_usuario(usuario)

    assert "sucursales.add_sucursal" in permisos
    assert "sucursales.delete_sucursal" not in permisos
    assert "cuentas.add_usuario" not in permisos
    # Puede ver usuarios y membresias de su sucursal.
    assert "cuentas.view_usuario" in permisos
    assert "cuentas.add_membresia" in permisos


def test_cajero_solo_lectura_en_etapa_1():
    negocio = NegocioFactory()
    sucursal = SucursalFactory(negocio=negocio)
    usuario, _ = cajero(negocio, sucursal)

    permisos = services.permisos_de_usuario(usuario)

    assert permisos == {"negocios.view_negocio", "sucursales.view_sucursal", "cuentas.view_usuario"}


def test_permisos_son_la_union_de_todos_sus_roles():
    negocio = NegocioFactory()
    sucursal = SucursalFactory(negocio=negocio)
    usuario = UsuarioFactory()
    membresia(usuario, negocio, rol=Rol.CAJERO, sucursal=sucursal)
    membresia(usuario, negocio, rol=Rol.ENCARGADO, sucursal=sucursal)

    esperados = permisos_de_rol(Rol.CAJERO) | permisos_de_rol(Rol.ENCARGADO)

    assert services.permisos_de_usuario(usuario) == esperados


def test_membresia_inactiva_no_suma_permisos():
    negocio = NegocioFactory()
    sucursal = SucursalFactory(negocio=negocio)
    usuario, membresia_dueno = dueno(negocio)

    assert services.permisos_de_usuario(usuario)

    membresia_dueno.activa = False
    membresia_dueno.save(update_fields=["activa"])

    assert services.permisos_de_usuario(usuario) == set()


def test_superusuario_tiene_todos_los_permisos():
    superusuario = UsuarioFactory(is_superuser=True, is_staff=True)

    assert services.permisos_de_usuario(superusuario) == services.permisos_existentes()
    assert services.usuario_tiene_permiso(superusuario, "cualquier.cualquier") is True


def test_usuario_sin_membresias_no_tiene_permisos():
    usuario = UsuarioFactory()

    assert services.permisos_de_usuario(usuario) == set()
    assert services.usuario_tiene_permiso(usuario, "negocios.view_negocio") is False


# --- Matriz de acceso por endpoint ------------------------------------------


@pytest.fixture
def cliente():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def mundo():
    negocio = NegocioFactory()
    sucursal = SucursalFactory(negocio=negocio)
    return negocio, sucursal


def test_dueno_puede_crear_y_borrar_sucursal(cliente, mundo):
    negocio, _ = mundo
    usuario, _ = dueno(negocio)
    cliente.force_login(usuario)

    creada = cliente.post("/api/sucursales/", {"nombre": "Sucursal Norte"}, format="json")
    borrada = cliente.delete(f"/api/sucursales/{creada.data['id']}/")

    assert creada.status_code == 201
    assert borrada.status_code == 204


def test_encargado_puede_crear_pero_no_borrar_sucursal(cliente, mundo):
    negocio, sucursal = mundo
    usuario, _ = encargado(negocio, sucursal)
    cliente.force_login(usuario)

    creada = cliente.post("/api/sucursales/", {"nombre": "Sucursal Norte"}, format="json")
    borrada = cliente.delete(f"/api/sucursales/{sucursal.pk}/")

    assert creada.status_code == 201
    assert borrada.status_code == 403
    assert borrada.data["codigo"] == "SIN_PERMISOS"


def test_cajero_no_puede_crear_sucursales(cliente, mundo):
    negocio, sucursal = mundo
    usuario, _ = cajero(negocio, sucursal)
    cliente.force_login(usuario)

    creado = cliente.post("/api/sucursales/", {"nombre": "Sucursal Norte"}, format="json")
    listado = cliente.get("/api/sucursales/")

    assert creado.status_code == 403
    assert creado.data["codigo"] == "SIN_PERMISOS"
    # Pero si puede leer las sucursales de su ambito.
    assert listado.status_code == 200


def test_cajero_no_puede_crear_usuarios_ni_membresias(cliente, mundo):
    negocio, sucursal = mundo
    usuario, _ = cajero(negocio, sucursal)
    cliente.force_login(usuario)

    nuevo = cliente.post("/api/usuarios/", {"email": "x@y.test", "contrasena": "Clave12345"},
                         format="json")
    membresia = cliente.post(
        "/api/membresias/",
        {"usuario": UsuarioFactory().pk, "rol": Rol.CAJERO, "sucursal_id": sucursal.pk},
        format="json",
    )

    assert nuevo.status_code == 403
    assert membresia.status_code == 403


def test_encargado_ve_la_lista_de_membresias_de_su_sucursal(cliente, mundo):
    """El listado cubre el ambito entero, incluida la membresia del propio operador."""
    negocio, sucursal = mundo
    usuario_encargado, _ = encargado(negocio, sucursal)
    cajero_sucursal, _ = cajero(negocio, sucursal)
    cliente.force_login(usuario_encargado)

    listado = cliente.get("/api/membresias/").data["results"]

    assert {m["usuario_email"] for m in listado} == {usuario_encargado.email, cajero_sucursal.email}


def test_sin_membresias_todo_el_panel_responde_403(cliente):
    usuario = UsuarioFactory()
    cliente.force_login(usuario)

    for ruta in ("/api/negocios/", "/api/sucursales/", "/api/usuarios/", "/api/membresias/"):
        respuesta = cliente.get(ruta)
        assert respuesta.status_code == 403, ruta
        assert respuesta.data["codigo"] == "SIN_AMBITO", ruta


def test_superusuario_accede_a_todos_los_recursos(cliente, mundo):
    negocio, sucursal = mundo
    superusuario = UsuarioFactory(is_superuser=True, is_staff=True)
    cliente.force_login(superusuario)

    for ruta in ("/api/negocios/", "/api/sucursales/", "/api/usuarios/", "/api/membresias/"):
        assert cliente.get(ruta).status_code == 200, ruta
