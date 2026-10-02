"""Tests de membresias: unicidad real, coherencia rol <-> sucursal y baja logica.

Las constraints se prueban contra PostgreSQL, no contra el `clean()` de Python: lo
que protege la base es la constraint.
"""
import pytest
from django.db import IntegrityError, transaction

from apps.core.exceptions import AmbitoInvalidoError, ConflictoError, SinAmbitoError
from apps.core.tests.factories import (
    NegocioFactory,
    SucursalFactory,
    UsuarioFactory,
    cajero,
    dueno,
    encargado,
    membresia,
)
from apps.cuentas import services
from apps.cuentas.models import Membresia
from apps.cuentas.roles import Rol
from apps.sucursales.models import Sucursal

pytestmark = pytest.mark.django_db


# --- Unicidad a nivel de base de datos -------------------------------------


def test_no_se_puede_duplicar_membresia_de_dueno_con_sucursal_null():
    negocio = NegocioFactory()
    usuario, _ = dueno(negocio)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Membresia.objects.create(
                usuario=usuario, negocio=negocio, sucursal=None, rol=Rol.DUENO
            )


def test_no_se_puede_duplicar_membresia_de_encargado():
    negocio = NegocioFactory()
    sucursal = SucursalFactory(negocio=negocio)
    usuario, _ = encargado(negocio, sucursal)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Membresia.objects.create(
                usuario=usuario, negocio=negocio, sucursal=sucursal, rol=Rol.ENCARGADO
            )


def test_mismo_usuario_puede_tener_mismo_rol_en_distinta_sucursal():
    negocio = NegocioFactory()
    centro = SucursalFactory(negocio=negocio)
    norte = SucursalFactory(negocio=negocio)
    usuario = UsuarioFactory()
    membresia(usuario, negocio, rol=Rol.CAJERO, sucursal=centro)
    membresia(usuario, negocio, rol=Rol.CAJERO, sucursal=norte)

    assert Membresia.objects.filter(usuario=usuario).count() == 2


def test_mismo_usuario_puede_ser_dueno_y_encargado():
    negocio = NegocioFactory()
    sucursal = SucursalFactory(negocio=negocio)
    usuario = UsuarioFactory()
    membresia(usuario, negocio, rol=Rol.DUENO)
    membresia(usuario, negocio, rol=Rol.ENCARGADO, sucursal=sucursal)

    roles = set(Membresia.objects.filter(usuario=usuario).values_list("rol", flat=True))

    assert roles == {Rol.DUENO, Rol.ENCARGADO}


# --- Coherencia rol <-> sucursal (CheckConstraint) --------------------------


@pytest.mark.parametrize("rol", [Rol.ENCARGADO, Rol.CAJERO])
def test_encargado_y_cajero_exigen_sucursal(rol):
    negocio = NegocioFactory()
    usuario = UsuarioFactory()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Membresia.objects.create(usuario=usuario, negocio=negocio, sucursal=None, rol=rol)


def test_dueno_no_puede_tener_sucursal():
    negocio = NegocioFactory()
    sucursal = SucursalFactory(negocio=negocio)
    usuario = UsuarioFactory()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Membresia.objects.create(
                usuario=usuario, negocio=negocio, sucursal=sucursal, rol=Rol.DUENO
            )


def test_la_sucursal_debe_pertenecer_al_negocio_de_la_membresia():
    """No se puede membresiar en la sucursal de otro negocio."""
    negocio_a = NegocioFactory()
    negocio_b = NegocioFactory()
    sucursal_b = SucursalFactory(negocio=negocio_b)
    usuario = UsuarioFactory()

    membresia_roto = Membresia(
        usuario=usuario, negocio=negocio_a, sucursal=sucursal_b, rol=Rol.CAJERO
    )
    with pytest.raises(Exception) as error:
        membresia_roto.full_clean()

    assert "sucursal" in str(error.value)


# --- Servicio de alta de membresias -----------------------------------------


def test_crear_membresia_resuelve_el_negocio_del_dueno():
    negocio = NegocioFactory()
    usuario_dueno, _ = dueno(negocio)
    nuevo = UsuarioFactory()

    creada = services.crear_membresia(
        usuario=nuevo, rol=Rol.DUENO, usuario_creador=usuario_dueno
    )

    assert creada.negocio_id == negocio.pk
    assert creada.sucursal_id is None


def test_crear_membresia_rechaza_negocio_ajeno():
    negocio_a = NegocioFactory()
    negocio_b = NegocioFactory()
    usuario_dueno, _ = dueno(negocio_a)
    nuevo = UsuarioFactory()

    with pytest.raises(AmbitoInvalidoError) as error:
        services.crear_membresia(
            usuario=nuevo, rol=Rol.DUENO, usuario_creador=usuario_dueno, negocio_id=negocio_b.pk
        )

    assert error.value.codigo == "AMBITO_INVALIDO"
    assert not Membresia.objects.filter(usuario=nuevo).exists()


def test_crear_membresia_rechaza_sucursal_ajena():
    negocio_a = NegocioFactory()
    negocio_b = NegocioFactory()
    sucursal_b = SucursalFactory(negocio=negocio_b)
    usuario_dueno, _ = dueno(negocio_a)
    nuevo = UsuarioFactory()

    with pytest.raises(AmbitoInvalidoError) as error:
        services.crear_membresia(
            usuario=nuevo,
            rol=Rol.CAJERO,
            usuario_creador=usuario_dueno,
            negocio_id=negocio_a.pk,
            sucursal_id=sucursal_b.pk,
        )

    assert error.value.codigo == "SUCURSAL_FUERA_DE_AMBITO"
    assert not Membresia.objects.filter(usuario=nuevo).exists()


def test_crear_membresia_duplicada_reporta_conflicto():
    negocio = NegocioFactory()
    sucursal = SucursalFactory(negocio=negocio)
    usuario_dueno, _ = dueno(negocio)
    nuevo = UsuarioFactory()

    servicios_crear = services.crear_membresia(
        usuario=nuevo, rol=Rol.CAJERO, usuario_creador=usuario_dueno,
        negocio_id=negocio.pk, sucursal_id=sucursal.pk,
    )
    with pytest.raises(ConflictoError) as error:
        services.crear_membresia(
            usuario=nuevo, rol=Rol.CAJERO, usuario_creador=usuario_dueno,
            negocio_id=negocio.pk, sucursal_id=sucursal.pk,
        )

    assert error.value.codigo == "MEMBRESIA_DUPLICADA"
    assert servicios_crear.pk is not None


def test_crear_membresia_de_sucursal_exige_indicar_sucursal_si_hay_varias():
    negocio = NegocioFactory()
    SucursalFactory(negocio=negocio)
    SucursalFactory(negocio=negocio)
    usuario_dueno, _ = dueno(negocio)
    nuevo = UsuarioFactory()

    with pytest.raises(AmbitoInvalidoError) as error:
        services.crear_membresia(
            usuario=nuevo, rol=Rol.CAJERO, usuario_creador=usuario_dueno, negocio_id=negocio.pk
        )

    assert error.value.codigo == "SUCURSAL_REQUERIDA"


def test_crear_membresia_de_sucursal_resuelve_si_el_operador_tiene_una_sola():
    negocio = NegocioFactory()
    sucursal = SucursalFactory(negocio=negocio)
    otra = SucursalFactory(negocio=negocio)
    usuario_dueno, _ = dueno(negocio)
    operador, _ = encargado(negocio, sucursal)
    nuevo = UsuarioFactory()

    creada = services.crear_membresia(
        usuario=nuevo, rol=Rol.CAJERO, usuario_creador=operador, negocio_id=negocio.pk
    )

    assert creada.sucursal_id == sucursal.pk
    assert creada.sucursal_id != otra.pk


def test_crear_membresia_exige_rol_valido():
    negocio = NegocioFactory()
    usuario_dueno, _ = dueno(negocio)

    with pytest.raises(AmbitoInvalidoError) as error:
        services.crear_membresia(
            usuario=UsuarioFactory(), rol="ADMIN", usuario_creador=usuario_dueno
        )

    assert error.value.codigo == "ROL_INVALIDO"


def test_crear_membresia_sin_ambito_del_operador():
    nuevo = UsuarioFactory()

    with pytest.raises(SinAmbitoError):
        services.crear_membresia(usuario=nuevo, rol=Rol.DUENO)


def test_crear_membresia_con_identificador_invalido():
    negocio = NegocioFactory()
    usuario_dueno, _ = dueno(negocio)

    with pytest.raises(AmbitoInvalidoError) as error:
        services.crear_membresia(
            usuario=UsuarioFactory(), rol=Rol.DUENO, usuario_creador=usuario_dueno,
            negocio_id="no-es-un-id",
        )

    assert error.value.codigo == "IDENTIFICADOR_INVALIDO"


# --- Baja logica ------------------------------------------------------------


def test_desactivar_membresia_no_la_borra():
    negocio = NegocioFactory()
    sucursal = SucursalFactory(negocio=negocio)
    operador, _ = dueno(negocio)
    usuario_cajero, membresia_cajero = cajero(negocio, sucursal)

    services.desactivar_membresia(membresia_cajero, operador)
    membresia_cajero.refresh_from_db()

    assert Membresia.objects.filter(pk=membresia_cajero.pk).exists()
    assert membresia_cajero.activa is False
    # Y con la membresia dada de baja, el usuario pierde el acceso a esa sucursal.
    assert list(Sucursal.objects.para_usuario(usuario_cajero)) == []


def test_desactivar_membresia_fuera_de_ambito():
    negocio_a = NegocioFactory()
    negocio_b = NegocioFactory()
    sucursal_b = SucursalFactory(negocio=negocio_b)
    operador, _ = dueno(negocio_a)
    _, membresia_b = cajero(negocio_b, sucursal_b)

    with pytest.raises(AmbitoInvalidoError):
        services.desactivar_membresia(membresia_b, operador)


def test_desactivar_usuario_no_puede_ser_uno_mismo():
    negocio = NegocioFactory()
    operador, _ = dueno(negocio)

    with pytest.raises(AmbitoInvalidoError) as error:
        services.desactivar_usuario(operador, operador)

    assert error.value.codigo == "AUTODEACTIVACION"


def test_desactivar_usuario_fuera_de_ambito():
    negocio_a = NegocioFactory()
    negocio_b = NegocioFactory()
    operador, _ = dueno(negocio_a)
    ajeno = UsuarioFactory()
    membresia(ajeno, negocio_b, rol=Rol.DUENO)

    with pytest.raises(AmbitoInvalidoError):
        services.desactivar_usuario(ajeno, operador)
