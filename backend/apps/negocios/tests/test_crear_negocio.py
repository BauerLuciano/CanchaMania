"""Tests del comando `crear_negocio` y de la via de arranque.

Este comando es la via documentada para el primer acceso al sistema, asi que antes
no tenia ninguna cobertura: el bug que rompia el flujo (la chicken-and-egg del primer
Dueno) solo aparecia al ejecutarlo de verdad.

Se prueba el comando completo y no solo el servicio, porque el orden de los pasos
dentro de la transaccion es parte del contrato: si algo falla, no puede quedar un
negocio huerfano ni un usuario sin membresia.
"""
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction

from apps.core.exceptions import ConflictoError
from apps.core.tests.factories import NegocioFactory, SucursalFactory, UsuarioFactory, dueno
from apps.cuentas import services
from apps.cuentas.models import Membresia, Usuario
from apps.cuentas.roles import Rol
from apps.negocios.models import Negocio
from apps.sucursales.models import Sucursal

pytestmark = pytest.mark.django_db


EMAIL_DUENO = "dueno@arranque.test"
CONTRASENA = "Clave-De-Prueba-123"


def ejecutar(**opciones):
    """Corre el comando como lo haria una persona, con la contrasena por parametro."""
    base = {
        "nombre": "Complejo Los Pinos",
        "email": EMAIL_DUENO,
        "contrasena": CONTRASENA,
    }
    return call_command("crear_negocio", **{**base, **opciones}, stdout=None, verbosity=0)


# --- Creacion exitosa -------------------------------------------------------


def test_crea_el_negocio_el_usuario_y_la_membresia_dueno():
    ejecutar()

    negocio = Negocio.objects.get()
    usuario = Usuario.objects.get(email=EMAIL_DUENO)

    assert negocio.nombre == "Complejo Los Pinos"
    # El slug se genera solo a partir del nombre.
    assert negocio.slug == "complejo-los-pinos"
    assert usuario.check_password(CONTRASENA)


def test_el_usuario_creador_queda_como_dueno_de_todo_el_negocio():
    ejecutar()

    negocio = Negocio.objects.get()
    usuario = Usuario.objects.get(email=EMAIL_DUENO)

    membresias = list(Membresia.objects.filter(usuario=usuario))
    assert len(membresias) == 1

    membresia = membresias[0]
    assert membresia.rol == Rol.DUENO
    # Ambito de Dueño = TODO el negocio, asi que nunca lleva sucursal.
    assert membresia.sucursal_id is None
    assert membresia.negocio_id == negocio.pk
    assert membresia.activa is True

    # Y el Dueño efectivamente accede: el ambito sale de la membresia activa.
    assert services.contexto_de(usuario).tiene_ambito is True
    assert services.contexto_de(usuario).tiene_rol(Rol.DUENO) is True


def test_crea_la_sucursal_inicial_cuando_se_pide():
    ejecutar(sucursal="Sucursal Apostoles")

    negocio = Negocio.objects.get()
    sucursal = Sucursal.objects.get()

    assert sucursal.nombre == "Sucursal Apostoles"
    assert sucursal.negocio_id == negocio.pk
    # La sucursal no cambia el ambito del Dueno: sigue siendo todo el negocio.
    assert Membresia.objects.get().sucursal_id is None


def test_sin_sucursal_no_crea_ninguna():
    ejecutar()

    assert Sucursal.objects.count() == 0


def test_el_dueno_creado_puede_iniciar_sesion():
    """El comando sirve para algo: el Dueño entra al sistema."""
    from apps.cuentas.services import iniciar_sesion, perfil_de

    ejecutar()

    usuario = iniciar_sesion(email=EMAIL_DUENO, contrasena=CONTRASENA)
    perfil = perfil_de(usuario)

    assert usuario.email == EMAIL_DUENO
    assert Rol.DUENO in perfil["roles"]
    # El Dueño ve los doce permisos del backend, no una lista inventada aca.
    assert "cuentas.delete_membresia" in perfil["permisos"]
    assert "sucursales.delete_sucursal" in perfil["permisos"]


# --- Sin duplicados ---------------------------------------------------------


def test_no_se_puede_repetir_el_email_del_dueno():
    UsuarioFactory(email=EMAIL_DUENO)

    with pytest.raises(ConflictoError) as error:
        ejecutar()

    assert error.value.codigo == "EMAIL_EN_USO"
    # Y no queda negocio huerfano de un intento fallido.
    assert Negocio.objects.count() == 0


def test_no_se_puede_repetir_el_nombre_del_negocio():
    ejecutar()

    with pytest.raises(ConflictoError) as error:
        ejecutar()

    assert error.value.codigo == "SLUG_EXISTENTE"
    # No se duplica el negocio ni se crea un segundo Dueño.
    assert Negocio.objects.count() == 1
    assert Usuario.objects.filter(email=EMAIL_DUENO).count() == 1


def test_la_via_de_origen_rechaza_a_un_usuario_que_ya_tiene_membresias():
    """La garantia que impide que la via de arranque sea un atajo de permisos."""
    negocio = NegocioFactory()
    usuario_existente, _ = dueno(negocio)
    negocio_vacio = NegocioFactory()

    with pytest.raises(ConflictoError) as error:
        services.crear_dueno_de_origen(usuario=usuario_existente, negocio=negocio_vacio)

    assert error.value.codigo == "MEMBRESIA_DUPLICADA"
    # Sigue teniendo solo la membresia que ya tenia.
    assert Membresia.objects.filter(usuario=usuario_existente).count() == 1


def test_la_via_de_origen_rechaza_a_un_negocio_que_ya_tiene_membresias():
    """Tampoco sirve para colar un segundo Dueño al lado del Dueño real."""
    negocio = NegocioFactory()
    dueno_real, _ = dueno(negocio)
    usuario_nuevo = UsuarioFactory()

    with pytest.raises(ConflictoError) as error:
        services.crear_dueno_de_origen(usuario=usuario_nuevo, negocio=negocio)

    assert error.value.codigo == "MEMBRESIA_DUPLICADA"
    assert Membresia.objects.filter(usuario=usuario_nuevo).count() == 0
    assert Membresia.objects.filter(negocio=negocio).count() == 1
    assert Membresia.objects.filter(negocio=negocio).first().usuario_id == dueno_real.pk


def test_la_via_de_origen_rechaza_una_membresia_inactiva_previa():
    """Aunque este inactiva, el usuario ya tiene membresia: no se usa de atajo."""
    negocio = NegocioFactory()
    sucursal = SucursalFactory(negocio=negocio)
    usuario = UsuarioFactory()
    Membresia.objects.create(
        usuario=usuario, negocio=negocio, sucursal=sucursal, rol=Rol.CAJERO, activa=False
    )

    with pytest.raises(ConflictoError) as error:
        services.crear_dueno_de_origen(usuario=usuario, negocio=NegocioFactory())

    assert error.value.codigo == "MEMBRESIA_DUPLICADA"


def test_la_constraint_de_postgres_sigue_siendo_el_backstop():
    """Aunque el chequeo previo pase, la base no admite dos Duenos iguales."""
    negocio = NegocioFactory()
    usuario = UsuarioFactory()

    services.crear_dueno_de_origen(usuario=usuario, negocio=negocio)

    # Se salta el chequeo de application y se va directo al `INSERT`.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Membresia.objects.create(
                usuario=usuario, negocio=negocio, sucursal=None, rol=Rol.DUENO
            )


def test_el_servicio_traduce_la_integrity_error_en_conflicto(monkeypatch):
    """La conversion de `IntegrityError` a 409 tambien esta en la via de origen."""
    negocio = NegocioFactory()
    usuario = UsuarioFactory()

    def revienta(*args, **kwargs):
        raise IntegrityError("llave duplicada viola restriccion de unicidad")

    monkeypatch.setattr(Membresia, "save", revienta)

    with pytest.raises(ConflictoError) as error:
        services.crear_dueno_de_origen(usuario=usuario, negocio=negocio)

    assert error.value.codigo == "MEMBRESIA_DUPLICADA"
    assert Membresia.objects.count() == 0


# --- Rollback ---------------------------------------------------------------


def test_si_falla_la_membresia_no_queda_nada_creado(monkeypatch):
    """Lo mas importante: si algo falla, no queda negocio ni usuario a medias."""
    def revienta(*args, **kwargs):
        raise ConflictoError("Fallo simulado al crear la membresia.", codigo="MEMBRESIA_DUPLICADA")

    monkeypatch.setattr("apps.negocios.management.commands.crear_negocio.crear_dueno_de_origen", revienta)

    with pytest.raises(ConflictoError):
        ejecutar(sucursal="Sucursal Apostoles")

    # La transaccion del comando se deshace entera.
    assert Negocio.objects.count() == 0
    assert Usuario.objects.filter(email=EMAIL_DUENO).count() == 0
    assert Sucursal.objects.count() == 0
    assert Membresia.objects.count() == 0


def test_si_falla_el_usuario_no_queda_negocio_creado(monkeypatch):
    def revienta(*args, **kwargs):
        raise ConflictoError("Fallo simulado al crear el usuario.", codigo="EMAIL_EN_USO")

    monkeypatch.setattr(
        "apps.negocios.management.commands.crear_negocio.crear_usuario", revienta
    )

    with pytest.raises(ConflictoError):
        ejecutar()

    assert Negocio.objects.count() == 0
    assert Membresia.objects.count() == 0


def test_si_falla_la_sucursal_no_queda_nada_creado(monkeypatch):
    """La sucursal se crea antes que la membresia: un fallo ahi tambien deshace todo."""
    def revienta(*args, **kwargs):
        raise ValueError("Fallo simulado al crear la sucursal.")

    monkeypatch.setattr(
        "apps.sucursales.models.Sucursal.objects.create", revienta, raising=True
    )

    with pytest.raises(ValueError):
        ejecutar(sucursal="Sucursal Apostoles")

    assert Negocio.objects.count() == 0
    assert Usuario.objects.filter(email=EMAIL_DUENO).count() == 0
    assert Sucursal.objects.count() == 0
    assert Membresia.objects.count() == 0


# --- Validaciones de la consola --------------------------------------------


def test_pide_contrasena_interactivamente_y_la_confirma(monkeypatch):
    """Sin `--contrasena` la pide y la confirma, para no dejarla en el historial."""
    pedidos = []

    def falso(prompt):
        pedidos.append(prompt)
        return "UnaClave" if len(pedidos) == 1 else "OtraClave"

    monkeypatch.setattr("getpass.getpass", falso)

    with pytest.raises(CommandError) as error:
        ejecutar(contrasena=None)

    assert "no coinciden" in str(error.value)
    assert len(pedidos) == 2
    assert Negocio.objects.count() == 0


def test_acepta_la_contrasena_confirmada_interactivamente(monkeypatch):
    monkeypatch.setattr("getpass.getpass", lambda prompt: CONTRASENA)

    ejecutar(contrasena=None)

    assert Usuario.objects.get(email=EMAIL_DUENO).check_password(CONTRASENA)


def test_no_admite_un_negocio_duplicado_por_slug():
    from apps.core.services import generar_slug

    negocio = NegocioFactory(slug=generar_slug("Complejo Los Pinos"))

    with pytest.raises(ConflictoError) as error:
        ejecutar()

    assert error.value.codigo == "SLUG_EXISTENTE"
    assert Negocio.objects.filter(slug=negocio.slug).count() == 1
    assert Usuario.objects.filter(email=EMAIL_DUENO).count() == 0
