"""Modelos de cuentas: Usuario y Membresia.

`Usuario` es el custom user del proyecto. Se define desde la Etapa 1 porque
cambiar el user model mas adelante obliga a una migracion de datos muy invasiva.

`Membresia` es la unica via de acceso a un negocio (SPEC §5 y §18):

    Usuario -> Membresia -> (Negocio, Sucursal?, Rol)

Modelo aprobado:

* Dueño     -> `sucursal_id IS NULL`     -> ambito sobre todo el negocio
* Encargado -> `sucursal_id` obligatoria  -> ambito sobre esa sucursal
* Cajero    -> `sucursal_id` obligatoria  -> ambito sobre esa sucursal

La cancha NO forma parte de la membresia (decisión aprobada).
"""
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.core.models import TenantScopedModel
from apps.core.scoping import Ambito
from apps.cuentas.roles import Rol


class Usuario(AbstractUser):
    """Usuario interno de CanchaMania.

    El login es por email (decisión aprobada): no existe `username`.
    `is_staff` / `is_superuser` conservan el Superadmin vía Django Admin (SPEC §5).
    """

    username = None

    email = models.EmailField("email", unique=True)

    first_name = models.CharField("nombre", max_length=150, blank=True)
    last_name = models.CharField("apellido", max_length=150, blank=True)
    telefono = models.CharField("telefono", max_length=32, blank=True)

    is_active = models.BooleanField("activo", default=True)

    creado_en = models.DateTimeField("creado", auto_now_add=True, db_index=True)
    actualizado_en = models.DateTimeField("actualizado", auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["email"]

    def __str__(self):
        return self.email

    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.email

    def get_short_name(self) -> str:
        return self.first_name or self.email


class Membresia(TenantScopedModel):
    """Vincula un usuario con un negocio, una sucursal opcional y un rol.

    Hereda `TenantScopedModel`, asi que el manager `objects.para_usuario(...)`
    ya la recorta por el ambito del usuario (aislamiento obligatorio).
    """

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="membresias",
        verbose_name="usuario",
    )
    negocio = models.ForeignKey(
        "negocios.Negocio",
        on_delete=models.CASCADE,
        related_name="membresias",
        verbose_name="negocio",
    )
    sucursal = models.ForeignKey(
        "sucursales.Sucursal",
        # PROTECT, no CASCADE: borrar la sede no debe borrar en silencio quien
        # tenia acceso a ella. La salida de siempre es desactivar la sucursal
        # (`activo=False`) y desactivar o dar de baja la membresia, que queda
        # registrada como historico. Igual que `Sucursal.negocio`.
        on_delete=models.PROTECT,
        related_name="membresias",
        verbose_name="sucursal",
        null=True,
        blank=True,
    )
    rol = models.CharField(
        "rol",
        max_length=16,
        choices=[(r, Rol.ETIQUETAS[r]) for r in Rol.TODOS],
    )
    activa = models.BooleanField("activa", default=True)

    class Meta:
        verbose_name = "membresia"
        verbose_name_plural = "membresias"
        ordering = ["negocio_id", "sucursal_id", "rol"]
        constraints = [
            # Unicidad real. En PostgreSQL los NULL no colisionan en un UNIQUE
            # normal, por eso hay dos constraints condicionales: la membresia de
            # Dueño (sucursal NULL) queda unica igual que la de Encargado/Cajero.
            models.UniqueConstraint(
                fields=["usuario", "negocio", "rol"],
                condition=Q(sucursal__isnull=True),
                name="uniq_membresia_negocio_sin_sucursal",
            ),
            models.UniqueConstraint(
                fields=["usuario", "negocio", "sucursal", "rol"],
                condition=Q(sucursal__isnull=False),
                name="uniq_membresia_negocio_con_sucursal",
            ),
            # Coherencia rol <-> sucursal segun el modelo aprobado.
            models.CheckConstraint(
                condition=(
                    (Q(rol=Rol.DUENO) & Q(sucursal__isnull=True))
                    | (Q(rol__in=[Rol.ENCARGADO, Rol.CAJERO]) & Q(sucursal__isnull=False))
                ),
                name="membresia_rol_consistente_con_sucursal",
            ),
        ]

    def __str__(self):
        alcance = self.sucursal.nombre if self.sucursal_id else "todo el negocio"
        return f"{self.usuario_id} @ {alcance} ({self.rol})"

    # -- Contrato de ambito (apps.core) --------------------------------------

    @classmethod
    def condicion_ambito(cls, ambito: Ambito) -> models.Q:
        """Una membresia es visible si cae dentro del alcance del ambito.

        Ambito de negocio completo (Dueño) -> todas las membresias del negocio.
        Ambito de sucursal (Encargado/Cajero) -> solo las de esa sucursal.
        """
        if ambito.sucursal_id is None:
            return models.Q(negocio_id=ambito.negocio_id)
        return models.Q(negocio_id=ambito.negocio_id, sucursal_id=ambito.sucursal_id)

    # -- Validaciones --------------------------------------------------------

    def clean(self):
        errores = {}

        if self.rol not in Rol.TODOS:
            errores["rol"] = "Rol desconocido."
        else:
            requiere_sucursal = Rol.REQUIERE_SUCURSAL[self.rol]
            if requiere_sucursal and self.sucursal_id is None:
                errores["sucursal"] = f"El rol {Rol.ETIQUETAS[self.rol]} requiere una sucursal."
            if not requiere_sucursal and self.sucursal_id is not None:
                errores["sucursal"] = (
                    "El rol Dueno se membresia sobre todo el negocio, sin sucursal."
                )

        # La sucursal debe pertenecer al mismo negocio de la membresia.
        if self.sucursal_id and self.negocio_id and self.sucursal.negocio_id != self.negocio_id:
            errores["sucursal"] = "La sucursal no pertenece al negocio indicado."

        if errores:
            raise ValidationError(errores)

    @property
    def ambito(self) -> Ambito:
        return Ambito(negocio_id=self.negocio_id, sucursal_id=self.sucursal_id, rol=self.rol)
