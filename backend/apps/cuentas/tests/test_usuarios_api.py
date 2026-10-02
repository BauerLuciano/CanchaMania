"""Tests de la API de usuarios y membresias del panel."""
import pytest

from apps.core.tests.factories import (
    NegocioFactory,
    SucursalFactory,
    UsuarioFactory,
    cajero,
    dueno,
    encargado,
)
from apps.cuentas.models import Membresia, Usuario

pytestmark = pytest.mark.django_db


@pytest.fixture
def cliente():
    from rest_framework.test import APIClient

    return APIClient()


# --- Usuarios ---------------------------------------------------------------


def test_dueno_crea_usuario_y_lo_asocia_con_una_membresia(cliente):
    negocio = NegocioFactory()
    sucursal = SucursalFactory(negocio=negocio)
    dueno_usuario, _ = dueno(negocio)
    cliente.force_login(dueno_usuario)

    creado = cliente.post(
        "/api/usuarios/",
        {"email": "Encargado@CanchaMania.test", "contrasena": "UnaClaveFuerte1", "nombre": "Ana"},
        format="json",
    )
    usuario_id = creado.data["id"]
    membresia = cliente.post(
        "/api/membresias/",
        {"usuario": usuario_id, "rol": "ENCARGADO", "negocio_id": negocio.pk, "sucursal_id": sucursal.pk},
        format="json",
    )

    assert creado.status_code == 201
    assert creado.data["email"] == "encargado@canchamania.test"
    assert "contrasena" not in creado.data
    assert membresia.status_code == 201
    assert membresia.data["rol"] == "ENCARGADO"
    assert Membresia.objects.get(usuario_id=usuario_id).sucursal_id == sucursal.pk


def test_no_se_devuelve_el_hash_de_la_contrasena(cliente):
    negocio = NegocioFactory()
    dueno_usuario, _ = dueno(negocio)
    cliente.force_login(dueno_usuario)

    creado = cliente.post(
        "/api/usuarios/", {"email": "nuevo@x.test", "contrasena": "UnaClaveFuerte1"}, format="json"
    )

    assert "password" not in creado.data
    assert Usuario.objects.get(pk=creado.data["id"]).password.startswith("pbkdf2_")


def test_email_duplicado_reporta_conflicto(cliente):
    negocio = NegocioFactory()
    dueno_usuario, _ = dueno(negocio)
    cliente.force_login(dueno_usuario)

    datos = {"email": "mismo@x.test", "contrasena": "UnaClaveFuerte1"}
    cliente.post("/api/usuarios/", datos, format="json")
    segundo = cliente.post("/api/usuarios/", datos, format="json")

    assert segundo.status_code == 409
    assert segundo.data["codigo"] == "EMAIL_EN_USO"


def test_contrasena_corta_es_rechazada(cliente):
    negocio = NegocioFactory()
    dueno_usuario, _ = dueno(negocio)
    cliente.force_login(dueno_usuario)

    respuesta = cliente.post(
        "/api/usuarios/", {"email": "corto@x.test", "contrasena": "123"}, format="json"
    )

    assert respuesta.status_code == 400
    assert respuesta.data["codigo"] == "VALIDACION_INVALIDA"
    assert "contrasena" in respuesta.data["detalles"]


def test_usuarios_solo_de_su_negocio(cliente):
    negocio_a, negocio_b = NegocioFactory(), NegocioFactory()
    dueno_a, _ = dueno(negocio_a)
    usuario_b, _ = dueno(negocio_b)
    cliente.force_login(dueno_a)

    listado = cliente.get("/api/usuarios/").data["results"]
    detalle_ajeno = cliente.get(f"/api/usuarios/{usuario_b.pk}/")

    assert [u["id"] for u in listado] == [dueno_a.pk]
    assert detalle_ajeno.status_code == 404


def test_encargado_ve_solo_usuarios_de_su_sucursal(cliente):
    negocio = NegocioFactory()
    centro = SucursalFactory(negocio=negocio)
    norte = SucursalFactory(negocio=negocio)
    operador, _ = encargado(negocio, centro)
    cliente.force_login(operador)
    su_cajero, _ = cajero(negocio, centro)
    cajero_otro, _ = cajero(negocio, norte)

    listado = cliente.get("/api/usuarios/").data["results"]

    assert {u["id"] for u in listado} == {operador.pk, su_cajero.pk}
    assert cajero_otro.pk not in {u["id"] for u in listado}


def test_desactivar_usuario_no_permite_el_borrado(cliente):
    negocio = NegocioFactory()
    dueno_usuario, _ = dueno(negocio)
    cliente.force_login(dueno_usuario)

    borrado = cliente.delete(f"/api/usuarios/{dueno_usuario.pk}/")

    assert borrado.status_code == 405
    assert Usuario.objects.filter(pk=dueno_usuario.pk).exists()


def test_desactivar_usuario_dentro_del_ambito(cliente):
    negocio = NegocioFactory()
    sucursal = SucursalFactory(negocio=negocio)
    dueno_usuario, _ = dueno(negocio)
    cliente.force_login(dueno_usuario)
    creado = cliente.post(
        "/api/usuarios/", {"email": "baja@x.test", "contrasena": "UnaClaveFuerte1"}, format="json"
    )
    cliente.post(
        "/api/membresias/",
        {"usuario": creado.data["id"], "rol": "CAJERO", "negocio_id": negocio.pk, "sucursal_id": sucursal.pk},
        format="json",
    )

    desactivado = cliente.post(f"/api/usuarios/{creado.data['id']}/desactivar/")

    assert desactivado.status_code == 200
    assert desactivado.data["is_active"] is False
    assert Usuario.objects.get(pk=creado.data["id"]).is_active is False


def test_no_se_puede_desactivar_un_usuario_de_otro_negocio(cliente):
    negocio_a, negocio_b = NegocioFactory(), NegocioFactory()
    dueno_a, _ = dueno(negocio_a)
    usuario_b, _ = dueno(negocio_b)
    cliente.force_login(dueno_a)

    respuesta = cliente.post(f"/api/usuarios/{usuario_b.pk}/desactivar/")

    assert respuesta.status_code == 404
    assert Usuario.objects.get(pk=usuario_b.pk).is_active is True


def test_editar_usuario_no_cambia_email_ni_activo(cliente):
    negocio = NegocioFactory()
    dueno_usuario, _ = dueno(negocio)
    objetivo, _ = dueno(negocio)
    cliente.force_login(dueno_usuario)

    respuesta = cliente.patch(
        f"/api/usuarios/{objetivo.pk}/",
        {"email": "hack@otro.test", "is_active": False, "nombre": "Nuevo"},
        format="json",
    )

    objetivo.refresh_from_db()
    assert respuesta.status_code == 200
    assert objetivo.email != "hack@otro.test"
    assert objetivo.is_active is True
    assert objetivo.first_name == "Nuevo"


# --- Membresias -------------------------------------------------------------


def test_encargado_no_puede_crear_membresia_de_dueno_para_usuario_ajeno(cliente):
    """Ni un rol de negocio completo ni sobre alguien de otro negocio."""
    negocio_a = NegocioFactory()
    sucursal_a = SucursalFactory(negocio=negocio_a)
    operador, _ = encargado(negocio_a, sucursal_a)
    usuario_b, _ = dueno(NegocioFactory())
    cliente.force_login(operador)

    respuesta = cliente.post(
        "/api/membresias/", {"usuario": usuario_b.pk, "rol": "DUENO", "negocio_id": negocio_a.pk},
        format="json",
    )

    assert respuesta.status_code == 403
    assert respuesta.data["codigo"] == "USUARIO_FUERA_DE_AMBITO"


def test_lista_de_membresias_del_dueno_incluye_sucursales(cliente):
    negocio = NegocioFactory()
    centro = SucursalFactory(negocio=negocio)
    dueno_usuario, _ = dueno(negocio)
    cliente.force_login(dueno_usuario)
    cliente.post(
        "/api/membresias/",
        {"usuario": UsuarioFactory().pk, "rol": "CAJERO", "negocio_id": negocio.pk, "sucursal_id": centro.pk},
        format="json",
    )

    listado = cliente.get("/api/membresias/").data["results"]
    roles = {m["rol"] for m in listado}

    assert roles == {"DUENO", "CAJERO"}


def test_no_se_puede_crear_membresia_para_usuario_de_otro_negocio(cliente):
    negocio_a, negocio_b = NegocioFactory(), NegocioFactory()
    sucursal_b = SucursalFactory(negocio=negocio_b)
    dueno_a, _ = dueno(negocio_a)
    usuario_b, _ = dueno(negocio_b)
    cliente.force_login(dueno_a)

    respuesta = cliente.post(
        "/api/membresias/",
        {"usuario": usuario_b.pk, "rol": "DUENO", "negocio_id": negocio_a.pk},
        format="json",
    )

    assert respuesta.status_code == 403
    assert respuesta.data["codigo"] == "USUARIO_FUERA_DE_AMBITO"
    assert Membresia.objects.filter(usuario=usuario_b).count() == 1


def test_no_se_puede_crear_membresia_en_negocio_ajeno(cliente):
    negocio_a, negocio_b = NegocioFactory(), NegocioFactory()
    dueno_a, _ = dueno(negocio_a)
    objetivo, _ = dueno(negocio_b)
    cliente.force_login(dueno_a)

    respuesta = cliente.post(
        "/api/membresias/", {"usuario": objetivo.pk, "rol": "CAJERO", "negocio_id": negocio_b.pk},
        format="json",
    )

    assert respuesta.status_code == 400  # el campo negocio solo ofrece negocios del ambito
    assert Membresia.objects.filter(usuario=objetivo).count() == 1


def test_desactivar_membresia_por_endpoint(cliente):
    negocio = NegocioFactory()
    sucursal = SucursalFactory(negocio=negocio)
    dueno_usuario, _ = dueno(negocio)
    cliente.force_login(dueno_usuario)
    creado = cliente.post(
        "/api/membresias/",
        {"usuario": UsuarioFactory().pk, "rol": "CAJERO", "negocio_id": negocio.pk, "sucursal_id": sucursal.pk},
        format="json",
    )

    borrada = cliente.delete(f"/api/membresias/{creado.data['id']}/")
    membresia = Membresia.objects.get(pk=creado.data["id"])

    assert borrada.status_code == 204
    assert membresia.activa is False


def test_membresia_ajena_no_se_puede_desactivar(cliente):
    negocio_a, negocio_b = NegocioFactory(), NegocioFactory()
    sucursal_b = SucursalFactory(negocio=negocio_b)
    dueno_a, _ = dueno(negocio_a)
    _, membresia_b = cajero(negocio_b, sucursal_b)
    cliente.force_login(dueno_a)

    respuesta = cliente.delete(f"/api/membresias/{membresia_b.pk}/")

    assert respuesta.status_code == 404
    assert Membresia.objects.get(pk=membresia_b.pk).activa is True


def test_encargado_no_puede_crear_membresia_de_dueno(cliente):
    """Dar el rol Dueno es elevate el alcance de una persona a todo el negocio."""
    negocio = NegocioFactory()
    sucursal = SucursalFactory(negocio=negocio)
    operador, _ = encargado(negocio, sucursal)
    cliente.force_login(operador)
    nuevo = UsuarioFactory()

    respuesta = cliente.post(
        "/api/membresias/", {"usuario": nuevo.pk, "rol": "DUENO", "negocio_id": negocio.pk},
        format="json",
    )

    assert respuesta.status_code == 403
    assert respuesta.data["codigo"] == "ROL_NO_ASIGNABLE"
    assert not Membresia.objects.filter(usuario=nuevo).exists()
