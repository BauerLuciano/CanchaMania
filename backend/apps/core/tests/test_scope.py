"""Tests de negocio y aislamiento.

Estos NO usan el cliente HTTP: aislan el comportamiento del manager, del ambito y
de los servicios, que es donde vive la garantia. Los endpoints se prueban en los
tests de cada app.
"""
import pytest

from apps.core.scoping import con_ambito, resolver_ambito
from apps.core.tests.factories import (
    NegocioFactory,
    SucursalFactory,
    UsuarioFactory,
    cajero,
    dueno,
    encargado,
    membresia,
)
from apps.negocios.models import Negocio
from apps.sucursales.models import Sucursal

pytestmark = pytest.mark.django_db


# --- Alcance por rol --------------------------------------------------------


def test_dueno_ve_todas_las_sucursales_de_su_negocio():
    negocio = NegocioFactory()
    centro = SucursalFactory(negocio=negocio)
    norte = SucursalFactory(negocio=negocio)
    usuario, _ = dueno(negocio)

    visibles = Sucursal.objects.para_usuario(usuario)

    assert set(visibles.values_list("pk", flat=True)) == {centro.pk, norte.pk}


def test_encargado_ve_solo_su_sucursal():
    negocio = NegocioFactory()
    centro = SucursalFactory(negocio=negocio)
    norte = SucursalFactory(negocio=negocio)
    usuario, _ = encargado(negocio, centro)

    visibles = Sucursal.objects.para_usuario(usuario)

    assert list(visibles.values_list("pk", flat=True)) == [centro.pk]


def test_cajero_ve_solo_su_sucursal():
    negocio = NegocioFactory()
    centro = SucursalFactory(negocio=negocio)
    norte = SucursalFactory(negocio=negocio)
    usuario, _ = cajero(negocio, centro)

    visibles = list(Sucursal.objects.para_usuario(usuario).values_list("pk", flat=True))

    assert visibles == [centro.pk]


# --- Aislamiento entre negocios --------------------------------------------


def test_usuario_no_ve_negocios_ajenos():
    negocio_a = NegocioFactory()
    negocio_b = NegocioFactory()
    usuario, _ = dueno(negocio_a)

    visibles = list(Negocio.objects.para_usuario(usuario).values_list("pk", flat=True))

    assert visibles == [negocio_a.pk]
    assert negocio_b.pk not in visibles


def test_usuario_no_ve_sucursales_de_otro_negocio_del_mismo_nombre():
    """Dos negocios con sucursales homonimas: el filtro no debe mezclarlos."""
    negocio_a = NegocioFactory()
    negocio_b = NegocioFactory()
    sucursal_a = SucursalFactory(negocio=negocio_a, nombre="Centro", slug="centro")
    sucursal_b = SucursalFactory(negocio=negocio_b, nombre="Centro", slug="centro")
    usuario, _ = dueno(negocio_a)

    visibles = list(Sucursal.objects.para_usuario(usuario).values_list("pk", flat=True))

    assert visibles == [sucursal_a.pk]
    assert sucursal_b.pk not in visibles


# --- Membresias multiples ----------------------------------------------------


def test_usuario_con_dos_membresias_ve_la_union_exacta():
    negocio_a = NegocioFactory()
    negocio_b = NegocioFactory()
    sucursal_a1 = SucursalFactory(negocio=negocio_a)
    sucursal_b1 = SucursalFactory(negocio=negocio_b)

    usuario = UsuarioFactory()
    membresia(usuario, negocio_a, rol="DUENO")
    membresia(usuario, negocio_b, rol="CAJERO", sucursal=sucursal_b1)

    visibles = set(Sucursal.objects.para_usuario(usuario).values_list("pk", flat=True))

    # El Dueño de A ve todas las sucursales de A; el Cajero de B solo la suya.
    assert visibles == {sucursal_a1.pk, sucursal_b1.pk}


def test_usuario_dueno_y_encargado_en_sucursales_distintas():
    negocio = NegocioFactory()
    centro = SucursalFactory(negocio=negocio)
    norte = SucursalFactory(negocio=negocio)
    usuario = UsuarioFactory()
    membresia(usuario, negocio, rol="DUENO")
    membresia(usuario, negocio, rol="ENCARGADO", sucursal=centro)

    contexto = resolver_ambito(usuario)
    roles = {a.rol for a in contexto.ambitos}

    assert roles == {"DUENO", "ENCARGADO"}
    # El ambito de Dueño sigueAmplio: no se restringe por tener tambien un rol de sucursal.
    visibles = set(Sucursal.objects.para_usuario(usuario).values_list("pk", flat=True))
    assert visibles == {centro.pk, norte.pk}


def test_usuario_sin_membresias_no_ve_nada():
    usuario = UsuarioFactory()

    assert list(Negocio.objects.para_usuario(usuario)) == []
    assert list(Sucursal.objects.para_usuario(usuario)) == []
    assert con_ambito(usuario).tiene_ambito() is False


def test_membresia_inactiva_no_otorga_acceso():
    negocio = NegocioFactory()
    sucursal = SucursalFactory(negocio=negocio)
    usuario, membresia_dueno = dueno(negocio)
    membresia(usuario, negocio, rol="ENCARGADO", sucursal=sucursal, activa=False)

    visibles = list(Sucursal.objects.para_usuario(usuario).values_list("pk", flat=True))

    assert visibles == [sucursal.pk]
    assert Negocio.objects.para_usuario(usuario).count() == 1

    # Y si la unica membresia esta inactiva, no entra nada.
    membresia_dueno.activa = False
    membresia_dueno.save(update_fields=["activa"])
    assert list(Negocio.objects.para_usuario(usuario)) == []
    assert list(Sucursal.objects.para_usuario(usuario)) == []


def test_superusuario_ve_todo():
    negocio_a = NegocioFactory()
    negocio_b = NegocioFactory()
    sucursal_b = SucursalFactory(negocio=negocio_b)
    superusuario = UsuarioFactory(is_superuser=True, is_staff=True)

    assert Negocio.objects.para_usuario(superusuario).count() == 2
    assert sucursal_b.pk in Sucursal.objects.para_usuario(superusuario).values_list(
        "pk", flat=True
    )


def test_usuario_staff_no_superusuario_no_ve_todo():
    """`is_staff` NO amplia el ambito: solo `is_superuser` (SPEC §5)."""
    negocio_a = NegocioFactory()
    negocio_b = NegocioFactory()
    staff = UsuarioFactory(is_staff=True)

    assert Negocio.objects.para_usuario(staff).count() == 0
    assert negocio_a.pk not in Negocio.objects.para_usuario(staff).values_list("pk", flat=True)


# --- Contexto de ambito -----------------------------------------------------


def test_contexto_calcula_negocios_y_sucursales():
    negocio = NegocioFactory()
    centro = SucursalFactory(negocio=negocio)
    usuario, _ = dueno(negocio)
    membresia(usuario, negocio, rol="CAJERO", sucursal=centro)

    contexto = resolver_ambito(usuario)

    assert contexto.negocio_ids == (negocio.pk,)
    assert contexto.sucursal_ids == (centro.pk,)
    assert contexto.roles == ("CAJERO", "DUENO")


def test_contexto_de_usuario_anonimo():
    contexto = resolver_ambito(None)

    assert contexto.tiene_ambito is False
    assert contexto.ambitos == ()
