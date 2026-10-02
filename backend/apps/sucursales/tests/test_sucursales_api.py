"""CRUD de sucursales, unicidad de slug y datos de la sucursal (SPEC §4.2)."""
import pytest
from django.db import IntegrityError, transaction

from apps.core.tests.factories import NegocioFactory, SucursalFactory, UsuarioFactory, dueno, encargado
from apps.sucursales.models import Sucursal

pytestmark = pytest.mark.django_db


@pytest.fixture
def cliente():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def dueno_con_negocio():
    negocio = NegocioFactory()
    usuario, _ = dueno(negocio)
    return usuario, negocio


# --- Alta -------------------------------------------------------------------


def test_crear_sucursal_genera_el_slug_del_nombre(cliente, dueno_con_negocio):
    usuario, negocio = dueno_con_negocio
    cliente.force_login(usuario)

    respuesta = cliente.post(
        "/api/sucursales/",
        {"nombre": "Sucursal Apóstoles", "telefono": "0373-123456", "direccion": "Av. Siempreviva 742"},
        format="json",
    )

    assert respuesta.status_code == 201
    # El slug se normaliza a ASCII, sin acentos (identificadores tecnicos).
    assert respuesta.data["slug"] == "sucursal-apostoles"
    assert respuesta.data["negocio"] == negocio.pk
    assert respuesta.data["zona_horaria"] == "America/Argentina/Buenos_Aires"
    assert respuesta.data["activo"] is True


def test_crear_sucursal_con_slug_explicito(cliente, dueno_con_negocio):
    usuario, _ = dueno_con_negocio
    cliente.force_login(usuario)

    respuesta = cliente.post(
        "/api/sucursales/", {"nombre": "Centro", "slug": "centro-norte"}, format="json"
    )

    assert respuesta.data["slug"] == "centro-norte"


def test_crear_sucursal_con_negocio_explicito_del_ambito(cliente):
    negocio_a, negocio_b = NegocioFactory(), NegocioFactory()
    usuario, _ = dueno(negocio_a)
    membresia_otro, _ = dueno(negocio_b)
    cliente.force_login(usuario)

    respuesta = cliente.post(
        "/api/sucursales/",
        {"nombre": "Sede B", "negocio": negocio_b.pk},
        format="json",
    )

    # El campo `negocio` solo ofrece los negocios del ambito: un id ajeno no es
    # siquiera una opcion valida para el serializer.
    assert respuesta.status_code == 400
    assert "negocio" in respuesta.data["detalles"]
    assert not Sucursal.objects.filter(negocio=negocio_b).exists()


def test_crear_sucursal_con_zona_horaria_invalida(cliente, dueno_con_negocio):
    usuario, _ = dueno_con_negocio
    cliente.force_login(usuario)

    respuesta = cliente.post(
        "/api/sucursales/", {"nombre": "Centro", "zona_horaria": "Marte/Olympus"}, format="json"
    )

    assert respuesta.status_code == 409
    assert respuesta.data["codigo"] == "ZONA_HORARIA_INVALIDA"


def test_crear_sucursal_acepta_otra_zona_horaria_valida(cliente, dueno_con_negocio):
    """La zona horaria es configurable por sucursal (SPEC §18)."""
    usuario, _ = dueno_con_negocio
    cliente.force_login(usuario)

    respuesta = cliente.post(
        "/api/sucursales/", {"nombre": "Sucursal Posadas", "zona_horaria": "America/Argentina/Cordoba"},
        format="json",
    )

    assert respuesta.status_code == 201
    assert respuesta.data["zona_horaria"] == "America/Argentina/Cordoba"


def test_crear_sucursal_sin_nombre(cliente, dueno_con_negocio):
    usuario, _ = dueno_con_negocio
    cliente.force_login(usuario)

    respuesta = cliente.post("/api/sucursales/", {}, format="json")

    assert respuesta.status_code == 400
    assert "nombre" in respuesta.data["detalles"]


# --- Slug unico por negocio (diagnostico: el slug puede repetirse entre negocios)


def test_slug_unico_dentro_del_negocio():
    negocio = NegocioFactory()
    SucursalFactory(negocio=negocio, slug="centro")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Sucursal.objects.create(negocio=negocio, nombre="Otra", slug="centro")


def test_el_mismo_slug_puede_existir_en_negocios_distintos():
    negocio_a, negocio_b = NegocioFactory(), NegocioFactory()
    SucursalFactory(negocio=negocio_a, slug="centro")
    SucursalFactory(negocio=negocio_b, slug="centro")

    assert Sucursal.objects.filter(slug="centro").count() == 2


def test_slug_duplicado_en_la_misma_sucursal_reporta_conflicto(cliente, dueno_con_negocio):
    usuario, negocio = dueno_con_negocio
    SucursalFactory(negocio=negocio, slug="centro")
    cliente.force_login(usuario)

    respuesta = cliente.post("/api/sucursales/", {"nombre": "Sede", "slug": "centro"}, format="json")

    assert respuesta.status_code == 409
    assert respuesta.data["codigo"] == "SLUG_EXISTENTE"
    assert Sucursal.objects.filter(negocio=negocio).count() == 1


# --- Lectura y edicion ------------------------------------------------------


def test_editar_sucursal_recalcula_el_slug_si_cambia_el_nombre(cliente, dueno_con_negocio):
    usuario, negocio = dueno_con_negocio
    sucursal = SucursalFactory(negocio=negocio, nombre="Centro", slug="centro")
    cliente.force_login(usuario)

    respuesta = cliente.patch(f"/api/sucursales/{sucursal.pk}/", {"nombre": "Norte"}, format="json")

    assert respuesta.status_code == 200
    assert respuesta.data["slug"] == "norte"


def test_editar_sucursal_mantiene_datos_no_enviados(cliente, dueno_con_negocio):
    usuario, negocio = dueno_con_negocio
    sucursal = SucursalFactory(
        negocio=negocio, nombre="Centro", slug="centro", telefono="0373-111", direccion="Calle 1"
    )
    cliente.force_login(usuario)

    cliente.patch(f"/api/sucursales/{sucursal.pk}/", {"nombre": "Centro Oeste"}, format="json")
    sucursal.refresh_from_db()

    assert sucursal.telefono == "0373-111"
    assert sucursal.direccion == "Calle 1"


def test_desactivar_sucursal(cliente, dueno_con_negocio):
    usuario, negocio = dueno_con_negocio
    sucursal = SucursalFactory(negocio=negocio)
    cliente.force_login(usuario)

    respuesta = cliente.patch(f"/api/sucursales/{sucursal.pk}/", {"activo": False}, format="json")

    assert respuesta.status_code == 200
    assert respuesta.data["activo"] is False


def test_baja_de_sucursal(cliente, dueno_con_negocio):
    usuario, negocio = dueno_con_negocio
    sucursal = SucursalFactory(negocio=negocio)
    cliente.force_login(usuario)

    respuesta = cliente.delete(f"/api/sucursales/{sucursal.pk}/")

    assert respuesta.status_code == 204
    assert not Sucursal.objects.filter(pk=sucursal.pk).exists()


def test_baja_con_membresias_associadas_reporta_conflicto(cliente, dueno_con_negocio):
    """Con datos asociados, la recomendacion es desactivar, no borrar."""
    from apps.core.tests.factories import membresia

    usuario, negocio = dueno_con_negocio
    sucursal = SucursalFactory(negocio=negocio)
    membresia(UsuarioFactory(), negocio, rol="CAJERO", sucursal=sucursal)
    cliente.force_login(usuario)

    respuesta = cliente.delete(f"/api/sucursales/{sucursal.pk}/")

    assert respuesta.status_code == 409
    assert respuesta.data["codigo"] == "SUCURSAL_CON_DEPENDENCIAS"
    assert Sucursal.objects.filter(pk=sucursal.pk).exists()


# --- Alcance de escritura ----------------------------------------------------


def test_encargado_crea_la_sucursal_dentro_del_negocio_de_su_sucursal(cliente):
    negocio = NegocioFactory()
    sucursal = SucursalFactory(negocio=negocio)
    operador, _ = encargado(negocio, sucursal)
    cliente.force_login(operador)

    respuesta = cliente.post("/api/sucursales/", {"nombre": "Nueva Sede"}, format="json")

    # El negocio se resuelve desde el ambito: nunca se elige desde el cuerpo.
    assert respuesta.status_code == 201
    assert respuesta.data["negocio"] == negocio.pk


def test_crear_sucursal_exige_permiso_add_sucursal(cliente):
    negocio = NegocioFactory()
    sucursal = SucursalFactory(negocio=negocio)
    from apps.core.tests.factories import cajero

    operador, _ = cajero(negocio, sucursal)
    cliente.force_login(operador)

    respuesta = cliente.post("/api/sucursales/", {"nombre": "No permitted"}, format="json")

    assert respuesta.status_code == 403
    assert respuesta.data["codigo"] == "SIN_PERMISOS"
    assert not Sucursal.objects.filter(nombre="No permitted").exists()
