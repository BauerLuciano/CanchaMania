"""Aislamiento entre sucursales del MISMO negocio.

Un Encargado o Cajero de la Sucursal A nunca debe poder tocar la Sucursal B del
mismo negocio si no tiene membresia para ella (SPEC §5).
"""
import pytest

from apps.core.tests.factories import NegocioFactory, SucursalFactory, UsuarioFactory, cajero, dueno, encargado
from apps.sucursales.models import Sucursal

pytestmark = pytest.mark.django_db


@pytest.fixture
def cliente():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def dos_sucursales():
    """Un negocio con Sucursal A y Sucursal B, cada una con su Encargado."""
    negocio = NegocioFactory(nombre="Complejo Los Pinos")
    sucursal_a = SucursalFactory(negocio=negocio, nombre="Apostoles", slug="apostoles")
    sucursal_b = SucursalFactory(negocio=negocio, nombre="Posadas", slug="posadas")
    encargado_a, membresia_a = encargado(negocio, sucursal_a)
    encargado_b, membresia_b = encargado(negocio, sucursal_b)
    return {
        "negocio": negocio,
        "sucursal_a": sucursal_a,
        "sucursal_b": sucursal_b,
        "encargado_a": encargado_a,
        "encargado_b": encargado_b,
    }


def test_encargado_ve_solo_su_sucursal_en_el_listado(cliente, dos_sucursales):
    cliente.force_login(dos_sucursales["encargado_a"])

    listado = cliente.get("/api/sucursales/").data["results"]

    assert [s["id"] for s in listado] == [dos_sucursales["sucursal_a"].pk]


def test_encargado_no_abre_la_otra_sucursal_del_mismo_negocio(cliente, dos_sucursales):
    cliente.force_login(dos_sucursales["encargado_a"])

    respuesta = cliente.get(f"/api/sucursales/{dos_sucursales['sucursal_b'].pk}/")

    assert respuesta.status_code == 404
    assert respuesta.data["codigo"] == "NO_ENCONTRADO"


def test_encargado_no_modifica_la_otra_sucursal(cliente, dos_sucursales):
    objetivo = dos_sucursales["sucursal_b"]
    cliente.force_login(dos_sucursales["encargado_a"])

    respuesta = cliente.patch(
        f"/api/sucursales/{objetivo.pk}/", {"nombre": "Secuestrada", "activo": False}, format="json"
    )

    objetivo.refresh_from_db()
    assert respuesta.status_code == 404
    assert objetivo.nombre == "Posadas"
    assert objetivo.activo is True


def test_encargado_no_borra_la_otra_sucursal(cliente, dos_sucursales):
    """Ni propia ni ajena: el rol Encargado no tiene `delete_sucursal`.

    El 403 no dice nada de la sucursal concreta: es la misma respuesta que
    recibiria si borrara la suya, asi que no confirma que exista.
    """
    objetivo = dos_sucursales["sucursal_b"]
    cliente.force_login(dos_sucursales["encargado_a"])

    ajena = cliente.delete(f"/api/sucursales/{objetivo.pk}/")
    propia = cliente.delete(f"/api/sucursales/{dos_sucursales['sucursal_a'].pk}/")

    assert ajena.status_code == propia.status_code == 403
    assert Sucursal.objects.filter(pk=objetivo.pk).exists()


def test_cajero_tampoco_accede_a_la_otra_sucursal(cliente, dos_sucursales):
    negocio = dos_sucursales["negocio"]
    sucursal_a = dos_sucursales["sucursal_a"]
    usuario_cajero, _ = cajero(negocio, sucursal_a)
    cliente.force_login(usuario_cajero)

    listado = cliente.get("/api/sucursales/")
    detalle = cliente.get(f"/api/sucursales/{dos_sucursales['sucursal_b'].pk}/")

    assert [s["id"] for s in listado.data["results"]] == [sucursal_a.pk]
    assert detalle.status_code == 404


def test_dueno_si_ve_todas_las_sucursales_de_su_negocio(cliente, dos_sucursales):
    negocio = dos_sucursales["negocio"]
    usuario_dueno, _ = dueno(negocio)
    cliente.force_login(usuario_dueno)

    listado = cliente.get("/api/sucursales/").data["results"]

    assert {s["id"] for s in listado} == {
        dos_sucursales["sucursal_a"].pk,
        dos_sucursales["sucursal_b"].pk,
    }


def test_encargado_con_dos_membresias_ve_las_dos_sucursales(cliente, dos_sucursales):
    """Varias membresias en el mismo negocio Amplian el alcance: es la union."""
    negocio = dos_sucursales["negocio"]
    usuario = dos_sucursales["encargado_a"]
    from apps.core.tests.factories import membresia

    membresia(usuario, negocio, rol="CAJERO", sucursal=dos_sucursales["sucursal_b"])
    cliente.force_login(usuario)

    listado = cliente.get("/api/sucursales/").data["results"]

    assert {s["id"] for s in listado} == {
        dos_sucursales["sucursal_a"].pk,
        dos_sucursales["sucursal_b"].pk,
    }


def test_encargado_no_ve_las_membresias_de_la_otra_sucursal(cliente, dos_sucursales):
    cliente.force_login(dos_sucursales["encargado_a"])

    listado = cliente.get("/api/membresias/").data["results"]
    usuarios = {m["usuario_email"] for m in listado}

    assert usuarios == {dos_sucursales["encargado_a"].email}


def test_encargado_no_ve_los_usuarios_de_la_otra_sucursal(cliente, dos_sucursales):
    cliente.force_login(dos_sucursales["encargado_a"])

    ids = {u["id"] for u in cliente.get("/api/usuarios/").data["results"]}

    assert ids == {dos_sucursales["encargado_a"].pk}


def test_dueno_tiene_membresia_de_negocio_y_ve_todas_las_membresias(cliente, dos_sucursales):
    negocio = dos_sucursales["negocio"]
    usuario_dueno, _ = dueno(negocio)
    cliente.force_login(usuario_dueno)

    listado = cliente.get("/api/membresias/").data["results"]

    # Los dos encargados de las dos sucursales mas la membresia de negocio del
    # propio Dueno: el listado responde "quien tiene acceso en mi ambito", y el
    # Dueeno tiene acceso a todo el negocio.
    assert len(listado) == 3
    assert {m["sucursal"] for m in listado} == {
        dos_sucursales["sucursal_a"].pk,
        dos_sucursales["sucursal_b"].pk,
        None,
    }


def test_usuario_sin_membresia_en_una_sucursal_inactiva_no_la_vee(cliente, dos_sucursales):
    negocio = dos_sucursales["negocio"]
    sucursal_a = dos_sucursales["sucursal_a"]
    encargado_a, membresia_a = encargado(negocio, sucursal_a)
    membresia_a.activa = False
    membresia_a.save(update_fields=["activa"])
    cliente.force_login(encargado_a)

    listado = cliente.get("/api/sucursales/")

    assert listado.status_code == 403
    assert listado.data["codigo"] == "SIN_AMBITO"
