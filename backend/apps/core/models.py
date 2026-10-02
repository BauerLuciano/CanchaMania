"""Modelos base de CanchaMania.

`TimeStampedModel` y `BaseModel` son utilidades puramente tecnicas.

`TenantScopedModel` es la pieza central del aislamiento multi-tenant (SPEC §5 y §22):
cada modelo de negocio declara como se construye la condicion SQL que limita una
fila a un ambito (negocio y, opcionalmente, sucursal) concreto. El resto del sistema
no reimplementa esa logica: usa `objects.para_usuario(...)`, que es el UNICO punto
de entrada a datos permitidos.
"""
from django.db import models

from apps.core.managers import ScopedManager
from apps.core.scoping import Ambito


class TimeStampedModel(models.Model):
    """Registra cuando se creo y cuando se modifico cada fila."""

    created_at = models.DateTimeField("creado", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        abstract = True


class BaseModel(TimeStampedModel):
    """Base comun a todos los modelos concretos del proyecto."""

    id = models.BigAutoField(primary_key=True)

    class Meta:
        abstract = True


class TenantScopedModel(BaseModel):
    """Modelo que pertenece a un ambito: un negocio y, opcionalmente, una sucursal.

    Las subclases implementan `condicion_ambito(ambito)`, que devuelve el `Q` que
    incluye una fila cuando el ambito la cubre. Con eso, el aislamiento queda
    resuelto en un unico lugar por modelo.
    """

    objects = ScopedManager()

    class Meta:
        abstract = True

    # -- Contrato de ambito -------------------------------------------------

    @classmethod
    def condicion_ambito(cls, ambito: Ambito) -> models.Q:
        """Q que incluye la fila si el ambito indicado la cubre."""
        raise NotImplementedError(f"{cls.__name__} debe implementar condicion_ambito(ambito).")

    @classmethod
    def condicion_ambitos(cls, ambitos) -> models.Q:
        """Q unificado para una coleccion de ambitos.

        Una lista de ambitos vacia produce un Q que no coincide con ninguna fila:
        un usuario sin membresias activas no puede ver nada.
        """
        condicion = models.Q(pk__in=[])
        for ambito in ambitos:
            condicion |= cls.condicion_ambito(ambito)
        return condicion

    def esta_en_ambito(self, ambito: Ambito) -> bool:
        """Indica si el ambito indicado cubre esta fila concreta."""
        return type(self).objects.filter(type(self).condicion_ambito(ambito), pk=self.pk).exists()
