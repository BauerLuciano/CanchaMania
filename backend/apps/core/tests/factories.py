"""Fabricas de test (`factory_boy`).

Todas las pruebas corren contra PostgreSQL: el aislamiento multi-tenant depende de
constraints reales (UniqueConstraint condicional, CheckConstraint, PROTECT) que
SQLite no reproduce igual.
"""
import factory
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory

from apps.cuentas.models import Membresia
from apps.cuentas.roles import Rol
from apps.negocios.models import Negocio
from apps.sucursales.models import Sucursal

Usuario = get_user_model()

CONTRASENA_TEST = "Clave-De-Prueba-123"


class UsuarioFactory(DjangoModelFactory):
    class Meta:
        model = Usuario
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"usuario{n}@canchamania.test")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    password = factory.PostGenerationMethodCall("set_password", CONTRASENA_TEST)
    is_active = True

    @classmethod
    def _after_postgeneration(cls, instance, create, results=None):
        if create:
            instance.save()


class NegocioFactory(DjangoModelFactory):
    class Meta:
        model = Negocio

    nombre = factory.Sequence(lambda n: f"Complejo Numero {n}")
    slug = factory.Sequence(lambda n: f"complejo-numero-{n}")
    activo = True


class SucursalFactory(DjangoModelFactory):
    class Meta:
        model = Sucursal

    negocio = factory.SubFactory(NegocioFactory)
    nombre = factory.Sequence(lambda n: f"Sucursal {n}")
    slug = factory.Sequence(lambda n: f"sucursal-{n}")
    telefono = factory.Faker("phone_number")
    direccion = factory.Faker("address")
    activo = True
    zona_horaria = "America/Argentina/Buenos_Aires"


class MembresiaFactory(DjangoModelFactory):
    """Membresia de Dueño por defecto: ambito sobre todo el negocio.

    Para Encargado o Cajero hay que pasar `sucursal=` ademas del `rol=`, porque el
    modelo aprobado exige sucursal para esos roles.
    """

    class Meta:
        model = Membresia

    usuario = factory.SubFactory(UsuarioFactory)
    negocio = factory.SubFactory(NegocioFactory)
    sucursal = None
    rol = Rol.DUENO
    activa = True


# --- Atajos que garantizan membresias validas -------------------------------


def membresia(usuario, negocio, rol=Rol.DUENO, sucursal=None, activa=True):
    from apps.cuentas.models import Membresia as _Membresia

    return _Membresia.objects.create(
        usuario=usuario, negocio=negocio, sucursal=sucursal, rol=rol, activa=activa
    )


def dueno(negocio, usuario=None):
    """Dueño del negocio: ambito sobre todo el negocio (sucursal NULL)."""
    usuario = usuario or UsuarioFactory()
    return usuario, membresia(usuario, negocio, rol=Rol.DUENO)


def encargado(negocio, sucursal, usuario=None):
    """Encargado de una sucursal: ambito acotado a esa sucursal."""
    usuario = usuario or UsuarioFactory()
    return usuario, membresia(usuario, negocio, rol=Rol.ENCARGADO, sucursal=sucursal)


def cajero(negocio, sucursal, usuario=None):
    """Cajero de una sucursal: ambito acotado a esa sucursal."""
    usuario = usuario or UsuarioFactory()
    return usuario, membresia(usuario, negocio, rol=Rol.CAJERO, sucursal=sucursal)
