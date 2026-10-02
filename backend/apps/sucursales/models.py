"""Modelo Sucursal / Complejo (SPEC §4.2 y §18).

Relacion: `Negocio 1---N Sucursal`. Nunca 1---1 (decisión aprobada).

`configuracion` operacional (horarios, dias de atencion, precios, reglas) NO se
agrega aca: pertenece a las etapas 2 y 8 (canchas, horarios, parametrizacion) y el
SPEC §6 prohibe hardcodear reglas comerciales. Se agrega cuando su etapa lo pida.
"""
from django.core.validators import MinLengthValidator
from django.db import models

from apps.core.models import TenantScopedModel
from apps.core.scoping import Ambito


class Sucursal(TenantScopedModel):
    """Sede operativa de un negocio."""

    negocio = models.ForeignKey(
        "negocios.Negocio",
        on_delete=models.PROTECT,
        related_name="sucursales",
        verbose_name="negocio",
    )
    nombre = models.CharField("nombre", max_length=150)
    slug = models.SlugField(
        "slug",
        max_length=80,
        validators=[MinLengthValidator(2)],
        help_text="Identificador dentro del negocio. Se genera del nombre si no se envia.",
    )
    telefono = models.CharField("telefono", max_length=32, blank=True)
    direccion = models.CharField("direccion", max_length=255, blank=True)
    activo = models.BooleanField(
        "activo",
        default=True,
        help_text="Una sucursal inactiva no ofrece disponibilidad (SPEC §4.2).",
    )
    zona_horaria = models.CharField(
        "zona horaria",
        max_length=64,
        default="America/Argentina/Buenos_Aires",
        help_text="Zona horaria IANA. Es configurable por sucursal (SPEC §18).",
    )

    class Meta:
        verbose_name = "sucursal"
        verbose_name_plural = "sucursales"
        ordering = ["negocio_id", "nombre"]
        constraints = [
            # Unico dentro del negocio. El mismo slug puede repetirse en negocios
            # distintos (diagnostico de Etapa 1).
            models.UniqueConstraint(
                fields=["negocio", "slug"], name="uniq_sucursal_slug_por_negocio"
            ),
            # No tiene sentido una sucursal sin negocio: protege de filas huerfanas
            # si alguien escribiera el FK a mano.
            models.CheckConstraint(
                condition=models.Q(negocio__isnull=False), name="sucursal_tiene_negocio"
            ),
        ]
        indexes = [models.Index(fields=["negocio", "nombre"], name="idx_sucursal_negocio")]

    def __str__(self):
        return f"{self.nombre} ({self.negocio_id})"

    @classmethod
    def condicion_ambito(cls, ambito: Ambito) -> models.Q:
        """Alcance del usuario sobre las sucursales.

        * Ambito de negocio (Dueño, `sucursal_id is None`) -> todas las del negocio.
        * Ambito de sucursal (Encargado/Cajero) -> unicamente esa sucursal.
        """
        if ambito.sucursal_id is None:
            return models.Q(negocio_id=ambito.negocio_id)
        return models.Q(negocio_id=ambito.negocio_id, pk=ambito.sucursal_id)
