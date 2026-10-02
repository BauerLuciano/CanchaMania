"""Modelo Negocio (SPEC §4.1 y §18).

Un negocio es el cliente de CanchaMania y concentra la pertenencia de todo lo
demas: sucursales, membresias y, mas adelante, Mercado Pago (SPEC §4.3).

Campos deliberadamente NO incluidos en la Etapa 1:

* `suscripcion` -> el SPEC §26 la deja como decision pendiente.
* credenciales de Mercado Pago -> etapa 5, y requieren cifrado (SPEC §22).
* `estado` -> el SPEC no define sus estados; `activo` alcanza como bandera tecnica.

No se inventa nada de esto: cuando se defina, se agrega aqui.
"""
from django.db import models

from apps.core.models import TenantScopedModel
from apps.core.scoping import Ambito


class Negocio(TenantScopedModel):
    """Cliente de CanchaMania."""

    nombre = models.CharField("nombre", max_length=150)
    slug = models.SlugField(
        "slug",
        max_length=80,
        unique=True,
        help_text="Identificador publico. Se genera del nombre si no se envia.",
    )
    activo = models.BooleanField("activo", default=True)

    class Meta:
        verbose_name = "negocio"
        verbose_name_plural = "negocios"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    @classmethod
    def condicion_ambito(cls, ambito: Ambito) -> models.Q:
        """El negocio es visible si el usuario tiene alguna membresia en el.

        Toda membresia resuelve su ambito sobre su negocio, asi que el filtro se
        reduce al id. Un usuario con membresias en A y B ve A y B; nunca mas.
        """
        return models.Q(pk=ambito.negocio_id)
