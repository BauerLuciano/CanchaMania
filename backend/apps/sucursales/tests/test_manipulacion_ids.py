"""Manipulacion de IDs: el caso de seguridad mas critico del SPEC §5.

"Todo usuario de Negocio A nunca debe poder leer, modificar o eliminar recursos de
Negocio B aunque conozca sus IDs."

Cada test intenta exactamente eso: usar IDs ajenos en la URL, en el cuerpo y en
los parametros de consulta, y verifica que el recurso NO se lee, NO se modifica y
NO se crea en el tenant equivocado.

Se cubren dos capas:

* la del serializer/viewset (lo que hace el frontend);
* la del servicio, llamada directo, para probar que el servicio tampoco depende de
  que el serializer haya filtrado antes.
"""
import pytest

from apps.core.exceptions import AmbitoInvalidoError
from apps.core.tests.factories import NegocioFactory, SucursalFactory, UsuarioFactory, dueno, encargado
from apps.sucursales import services as sucursal_services
from apps.sucursales.models import Sucursal

pytestmark = pytest.mark.django_db


@pytest.fixture
def cliente():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def dos_tenant():
    """Negocio A (usuario A) y Negocio B (usuario B), con sucursal cada uno."""
    negocio_a = NegocioFactory(nombre="Complejo A")
    sucursal_a = SucursalFactory(negocio=negocio_a, nombre="Sede A", slug="sede-a")
    usuario_a, _ = dueno(negocio_a, usuario=UsuarioFactory())

    negocio_b = NegocioFactory(nombre="Complejo B")
    sucursal_b = SucursalFactory(negocio=negocio_b, nombre="Sede B", slug="sede-b")
    usuario_b, _ = dueno(negocio_b)

    return {
        "usuario_a": usuario_a,
        "negocio_a": negocio_a,
        "sucursal_a": sucursal_a,
        "usuario_b": usuario_b,
        "negocio_b": negocio_b,
        "sucursal_b": sucursal_b,
    }


# --- Lectura por URL manipulada ---------------------------------------------


def test_url_de_negocio_ajeno_no_sirve_para_leer(dos_tenant):
    from rest_framework.test import APIClient

    cliente = APIClient()
    cliente.force_login(dos_tenant["usuario_a"])

    assert cliente.get(f"/api/negocios/{dos_tenant['negocio_b'].pk}/").status_code == 404
    assert cliente.get(f"/api/sucursales/{dos_tenant['sucursal_b'].pk}/").status_code == 404
    assert cliente.get(f"/api/membresias/999999/").status_code == 404


# --- Escritura: no se crea nada en un negocio ajeno -------------------------


def test_crear_sucursal_con_negocio_ajeno_se_rechaza_y_no_crea_nada(cliente, dos_tenant):
    cliente.force_login(dos_tenant["usuario_a"])

    respuesta = cliente.post(
        "/api/sucursales/",
        {"nombre": "Infiltrada", "negocio": dos_tenant["negocio_b"].pk},
        format="json",
    )
    sucursal_b = dos_tenant["sucursal_b"]

    assert respuesta.status_code == 400
    assert "negocio" in respuesta.data["detalles"]
    assert not Sucursal.objects.filter(nombre="Infiltrada").exists()
    assert Sucursal.objects.filter(negocio=dos_tenant["negocio_b"]).count() == 1


def test_crear_sucursal_sin_negocio_cae_en_su_negocio(cliente, dos_tenant):
    """Si no se manda negocio, el backend lo deduce del ambito: nunca del cliente."""
    cliente.force_login(dos_tenant["usuario_a"])

    respuesta = cliente.post("/api/sucursales/", {"nombre": "Sede Nueva"}, format="json")

    assert respuesta.status_code == 201
    assert respuesta.data["negocio"] == dos_tenant["negocio_a"].pk


def test_crear_sucursal_con_negocio_de_tercero_devuelve_403_si_llega_al_servicio(dos_tenant):
    """El servicio tampoco confía: se llama directo, saltandose el serializer."""
    with pytest.raises(AmbitoInvalidoError) as error:
        sucursal_services.valores_de_creacion(
            datos={"nombre": "Infiltrada", "negocio": dos_tenant["negocio_b"]},
            usuario=dos_tenant["usuario_a"],
        )

    assert error.value.codigo == "AMBITO_INVALIDO"
    assert not Sucursal.objects.filter(nombre="Infiltrada").exists()


# --- Escritura: una sucursal no cambia de negocio ---------------------------


def test_una_sucursal_no_se_mueve_de_negocio_con_patch(cliente, dos_tenant):
    objetivo = dos_tenant["sucursal_a"]
    cliente.force_login(dos_tenant["usuario_a"])

    respuesta = cliente.patch(
        f"/api/sucursales/{objetivo.pk}/",
        {"negocio": dos_tenant["negocio_b"].pk, "nombre": "Movida"},
        format="json",
    )
    objetivo.refresh_from_db()

    assert respuesta.status_code == 400  # negocio ajeno no es opcion valida
    assert objetivo.negocio_id == dos_tenant["negocio_a"].pk
    assert objetivo.nombre == "Sede A"


def test_mover_de_negocio_se_rechaza_aunque_llegue_al_servicio(dos_tenant):
    objetivo = dos_tenant["sucursal_a"]

    with pytest.raises(AmbitoInvalidoError) as error:
        sucursal_services.valores_de_actualizacion(
            instancia=objetivo,
            datos={"negocio": dos_tenant["negocio_b"]},
            usuario=dos_tenant["usuario_a"],
        )

    objetivo.refresh_from_db()
    assert error.value.codigo == "AMBITO_INVALIDO"
    assert objetivo.negocio_id == dos_tenant["negocio_a"].pk


def test_no_se_puede_editar_una_sucursal_de_otro_negocio_por_servicio(dos_tenant):
    objetivo = dos_tenant["sucursal_b"]

    with pytest.raises(AmbitoInvalidoError):
        sucursal_services.valores_de_actualizacion(
            instancia=objetivo, datos={"nombre": "Secuestrada"}, usuario=dos_tenant["usuario_a"]
        )

    objetivo.refresh_from_db()
    assert objetivo.nombre == "Sede B"


def test_no_se_puede_borrar_una_sucursal_de_otro_negocio_por_servicio(dos_tenant):
    objetivo = dos_tenant["sucursal_b"]

    with pytest.raises(AmbitoInvalidoError):
        sucursal_services.eliminar(instancia=objetivo, usuario=dos_tenant["usuario_a"])

    assert Sucursal.objects.filter(pk=objetivo.pk).exists()


# --- Membresias: no se puede dar de alta gente en otro negocio --------------


def test_no_se_puede_crear_membresia_con_sucursal_de_otro_negocio(cliente, dos_tenant):
    usuario_destino, _ = dueno(dos_tenant["negocio_b"])
    cliente.force_login(dos_tenant["usuario_a"])

    respuesta = cliente.post(
        "/api/membresias/",
        {
            "usuario": usuario_destino.pk,
            "rol": "CAJERO",
            "negocio_id": dos_tenant["negocio_a"].pk,
            "sucursal_id": dos_tenant["sucursal_b"].pk,
        },
        format="json",
    )

    # La sucursal ajena no es ni una opcion del formulario: el campo responde como
    # valor invalido (400). El servicio igual la rechazaria con 403 si llegara.
    assert respuesta.status_code == 400
    assert respuesta.data["codigo"] == "VALIDACION_INVALIDA"
    assert "sucursal_id" in respuesta.data["detalles"]


def test_no_se_puede_crear_membresia_de_dueno_para_usuario_ajeno(cliente, dos_tenant):
    _, membresia_b = dueno(dos_tenant["negocio_b"])
    cliente.force_login(dos_tenant["usuario_a"])

    respuesta = cliente.post(
        "/api/membresias/",
        {"usuario": membresia_b.usuario_id, "rol": "DUENO", "negocio_id": dos_tenant["negocio_a"].pk},
        format="json",
    )

    assert respuesta.status_code == 403
    assert respuesta.data["codigo"] == "USUARIO_FUERA_DE_AMBITO"


# --- Parametros de consulta: filtros del cliente se ignoran -----------------


def test_los_filtros_por_negocio_del_cliente_se_ignoran(cliente, dos_tenant):
    """Un `?negocio=<ajeno>` no cambia el resultado: el queryset ya viene recortado."""
    cliente.force_login(dos_tenant["usuario_a"])

    listado = cliente.get(f"/api/sucursales/?negocio={dos_tenant['negocio_b'].pk}").data["results"]

    assert [s["id"] for s in listado] == [dos_tenant["sucursal_a"].pk]


def test_el_id_de_la_url_rige_sobre_el_negocio_indicado_en_el_cuerpo(cliente, dos_tenant):
    """El recurso de la URL manda; un negocio propio distinto se descarta."""
    objetivo = dos_tenant["sucursal_a"]
    cliente.force_login(dos_tenant["usuario_a"])

    respuesta = cliente.patch(
        f"/api/sucursales/{objetivo.pk}/",
        {"negocio": dos_tenant["negocio_a"].pk, "nombre": "Renombrada OK"},
        format="json",
    )
    objetivo.refresh_from_db()

    assert respuesta.status_code == 200
    assert respuesta.data["negocio"] == dos_tenant["negocio_a"].pk
    assert objetivo.nombre == "Renombrada OK"


# --- Aislamiento dentro del mismo negocio, entre sucursales -----------------


def test_encargado_no_puede_tocar_la_otra_sucursal_del_mismo_negocio_por_url(cliente):
    negocio = NegocioFactory()
    sucursal_a = SucursalFactory(negocio=negocio, slug="a")
    sucursal_b = SucursalFactory(negocio=negocio, slug="b")
    operador, _ = encargado(negocio, sucursal_a)
    cliente.force_login(operador)

    # Lectura y edicion: 404, el recurso esta fuera del ambito y no se confirma
    # que exista. Borrado: 403, porque el rol Encargado no tiene `delete_sucursal`
    # para ninguna sucursal, propia o ajena.
    assert cliente.get(f"/api/sucursales/{sucursal_b.pk}/").status_code == 404
    assert cliente.patch(f"/api/sucursales/{sucursal_b.pk}/", {"nombre": "X"}, format="json").status_code == 404
    assert cliente.delete(f"/api/sucursales/{sucursal_b.pk}/").status_code == 403
    # El nombre de la factory lleva un contador global de la sesion de tests, asi
    # que se compara contra el valor previo y no contra un literal.
    assert sucursal_b.nombre.startswith("Sucursal ")
    assert not Sucursal.objects.filter(pk=sucursal_b.pk, nombre="X").exists()
