"""Aislamiento entre negocios.

Caso critico del SPEC §5: un usuario de Negocio A nunca debe poder leer, modificar
ni eliminar recursos del Negocio B, aunque conozca todos los IDs.
"""
import pytest

from apps.core.tests.factories import NegocioFactory, SucursalFactory, UsuarioFactory, dueno
from apps.negocios.models import Negocio

pytestmark = pytest.mark.django_db


@pytest.fixture
def cliente():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def dos_negocios():
    """Negocio A con dos sucursales y un Dueño; Negocio B con una y otro Dueño."""
    negocio_a = NegocioFactory(nombre="Complejo Los Pinos")
    sucursal_a1 = SucursalFactory(negocio=negocio_a, nombre="Apostoles", slug="apostoles")
    sucursal_a2 = SucursalFactory(negocio=negocio_a, nombre="Posadas", slug="posadas")
    usuario_a, _ = dueno(negocio_a)

    negocio_b = NegocioFactory(nombre="Complejo Del Sur")
    sucursal_b = SucursalFactory(negocio=negocio_b, nombre="Centro", slug="centro")
    usuario_b, _ = dueno(negocio_b)

    return {
        "negocio_a": negocio_a,
        "sucursal_a1": sucursal_a1,
        "sucursal_a2": sucursal_a2,
        "usuario_a": usuario_a,
        "negocio_b": negocio_b,
        "sucursal_b": sucursal_b,
        "usuario_b": usuario_b,
    }


def test_lista_solo_muestra_los_negocios_del_usuario(cliente, dos_negocios):
    cliente.force_login(dos_negocios["usuario_a"])

    respuesta = cliente.get("/api/negocios/")

    assert respuesta.status_code == 200
    assert [n["id"] for n in respuesta.data["results"]] == [dos_negocios["negocio_a"].pk]


def test_detalle_de_negocio_ajeno_devuelve_404(cliente, dos_negocios):
    cliente.force_login(dos_negocios["usuario_a"])

    respuesta = cliente.get(f"/api/negocios/{dos_negocios['negocio_b'].pk}/")

    assert respuesta.status_code == 404
    assert respuesta.data["codigo"] == "NO_ENCONTRADO"


def test_no_puede_modificar_un_negocio_ajeno(cliente, dos_negocios):
    cliente.force_login(dos_negocios["usuario_a"])
    objetivo = dos_negocios["negocio_b"]

    respuesta = cliente.patch(
        f"/api/negocios/{objetivo.pk}/", {"nombre": "Robado", "activo": False}, format="json"
    )

    objetivo.refresh_from_db()
    # 405 y no 403 ni 404: el recurso no admite escritura en la Etapa 1, asi que
    # la respuesta no depende de que el negocio sea ajeno o propio.
    assert respuesta.status_code == 405
    assert objetivo.nombre == "Complejo Del Sur"
    assert objetivo.activo is True


def test_no_puede_borrar_un_negocio_ajeno(cliente, dos_negocios):
    cliente.force_login(dos_negocios["usuario_a"])
    objetivo = dos_negocios["negocio_b"]

    respuesta = cliente.delete(f"/api/negocios/{objetivo.pk}/")

    assert respuesta.status_code == 405  # el recurso es de solo lectura en la Etapa 1
    assert Negocio.objects.filter(pk=objetivo.pk).exists()


def test_negocios_es_de_solo_lectura(cliente, dos_negocios):
    cliente.force_login(dos_negocios["usuario_a"])

    creado = cliente.post(
        "/api/negocios/", {"nombre": "Negocio Inventado"}, format="json"
    )
    editado = cliente.patch(
        f"/api/negocios/{dos_negocios['negocio_a'].pk}/", {"nombre": "Otro"}, format="json"
    )

    assert creado.status_code == 405
    assert editado.status_code == 405
    dos_negocios["negocio_a"].refresh_from_db()
    assert dos_negocios["negocio_a"].nombre == "Complejo Los Pinos"


def test_usuario_con_membresias_en_dos_negocios_ve_solo_esos_dos(cliente):
    negocio_a, negocio_b, negocio_c = (
        NegocioFactory(),
        NegocioFactory(),
        NegocioFactory(),
    )
    usuario, _ = dueno(negocio_a)
    from apps.core.tests.factories import membresia

    membresia(usuario, negocio_b, rol="DUENO")

    cliente.force_login(usuario)
    ids = {n["id"] for n in cliente.get("/api/negocios/").data["results"]}

    assert ids == {negocio_a.pk, negocio_b.pk}
    assert negocio_c.pk not in ids


def test_usuario_sin_membresias_no_accede_a_la_api_de_negocios(cliente):
    cliente.force_login(UsuarioFactory())

    respuesta = cliente.get("/api/negocios/")

    assert respuesta.status_code == 403
    assert respuesta.data["codigo"] == "SIN_AMBITO"


def test_negocio_con_sucursales_no_se_toca_al_intentar_borrarlo(cliente):
    """`Sucursal.negocio` es PROTECT: nada de esto puede dejar huerfana una sede."""
    negocio = NegocioFactory()
    SucursalFactory(negocio=negocio)
    usuario, _ = dueno(negocio)
    cliente.force_login(usuario)

    respuesta = cliente.delete(f"/api/negocios/{negocio.pk}/")

    assert respuesta.status_code == 405
    assert Negocio.objects.filter(pk=negocio.pk).exists()


def test_slugs_de_negocios_son_globales_y_unicos():
    negocio = NegocioFactory(slug="complejo-los-pinos")

    with pytest.raises(Exception):
        Negocio.objects.create(nombre="Otro", slug="complejo-los-pinos")
