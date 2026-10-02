"""Resolucion de ambito multi-tenant.

Un `Ambito` es la unidad de acceso que otorga una membresia activa:

    (negocio_id, sucursal_id, rol)

* `sucursal_id is None` -> ambito sobre TODO el negocio (rol Dueño);
* `sucursal_id = X`     -> ambito sobre esa sucursal (rol Encargado o Cajero).

El ambito SIEMPRE se deriva del usuario autenticado y de sus membresías activas.
Nunca de un `negocio_id` o `sucursal_id` recibido del cliente.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from django.db.models import QuerySet

from apps.core.exceptions import SinAmbitoError


@dataclass(frozen=True, order=True)
class Ambito:
    """Un ambito de acceso derivado de una membresia activa."""

    negocio_id: int
    sucursal_id: int | None = None
    rol: str = ""

    @property
    def es_todo_el_negocio(self) -> bool:
        return self.sucursal_id is None

    def clave(self) -> tuple[int, int | None]:
        """Identidad del ambito sin el rol, para agrupar por negocio/sucursal."""
        return (self.negocio_id, self.sucursal_id)


@dataclass(frozen=True)
class ContextoDeAmbito:
    """Resultado de resolver el ambito de un usuario."""

    usuario_id: int | None
    es_superusuario: bool
    ambitos: tuple[Ambito, ...]

    @property
    def tiene_ambito(self) -> bool:
        return self.es_superusuario or bool(self.ambitos)

    @property
    def negocio_ids(self) -> tuple[int, ...]:
        return tuple(sorted({a.negocio_id for a in self.ambitos}))

    @property
    def sucursal_ids(self) -> tuple[int, ...]:
        """Sucursales con acceso acotado a una en particular.

        No incluye las sucursales cubiertas por un ambito de negocio completo.
        """
        return tuple(sorted({a.sucursal_id for a in self.ambitos if a.sucursal_id is not None}))

    @property
    def roles(self) -> tuple[str, ...]:
        return tuple(sorted({a.rol for a in self.ambitos if a.rol}))

    def tiene_rol(self, rol: str) -> bool:
        """True si el usuario tiene algun ambito con ese rol.

        El superusuario tiene todos los roles: administra globalmente (SPEC §5).
        """
        if self.es_superusuario:
            return True
        return any(a.rol == rol for a in self.ambitos)

    def negocio_cubierto(self, negocio_id: int) -> bool:
        """True si el usuario tiene algun ambito dentro de ese negocio."""
        return any(a.negocio_id == negocio_id for a in self.ambitos)

    def sucursal_abierta(self, negocio_id: int, sucursal_id: int) -> bool:
        """True si el usuario tiene algun ambito dentro de esa sucursal."""
        return any(
            a.negocio_id == negocio_id and (a.sucursal_id is None or a.sucursal_id == sucursal_id)
            for a in self.ambitos
        )

    def sucursales_de_negocio(self, negocio_id: int) -> list[int] | None:
        """Sucursales visibles del negocio, o None si tiene todo el negocio.

        Devolver None significa "sin restriccion de sucursal": el llamador debe
        entonces aplicar unicamente el filtro por negocio.
        """
        if not self.negocio_cubierto(negocio_id):
            return []
        if any(a.negocio_id == negocio_id and a.sucursal_id is None for a in self.ambitos):
            return None
        return sorted(
            {a.sucursal_id for a in self.ambitos if a.negocio_id == negocio_id and a.sucursal_id}
        )

    def unico_negocio_id(self) -> int | None:
        """Negocio unico del ambito, o None si hay varios o ninguno."""
        ids = self.negocio_ids
        return ids[0] if len(ids) == 1 else None


class _UsuarioConAmbito:
    """Envoltura perezosa para no repetir la consulta de membresias."""

    __slots__ = ("_usuario", "_contexto")

    def __init__(self, usuario):
        self._usuario = usuario
        self._contexto = None

    @property
    def contexto(self) -> ContextoDeAmbito:
        if self._contexto is None:
            self._contexto = resolver_ambito(self._usuario)
        return self._contexto

    @property
    def ambitos(self) -> Sequence[Ambito]:
        return self.contexto.ambitos

    def tiene_ambito(self) -> bool:
        return self.contexto.tiene_ambito

    def exigir_ambito(self) -> ContextoDeAmbito:
        if not self.contexto.tiene_ambito:
            raise SinAmbitoError()
        return self.contexto


def con_ambito(usuario) -> _UsuarioConAmbito:
    """Punto de entrada unico para obtener el ambito de un usuario."""
    if usuario is None or not getattr(usuario, "is_authenticated", False):
        return _UsuarioConAmbito(None)
    return _UsuarioConAmbito(usuario)


def _ambitos_desde_membresias(membresias: Iterable) -> tuple[Ambito, ...]:
    return tuple(
        Ambito(negocio_id=m.negocio_id, sucursal_id=m.sucursal_id, rol=m.rol)
        for m in membresias
    )


def resolver_ambito(usuario) -> ContextoDeAmbito:
    """Construye el contexto de ambito del usuario a partir de sus membresias activas.

    Solo se consideran membresias con `activa=True`. Una membresia inactiva no
    otorga ningun acceso (test: membresias inactivas deniegan acceso).
    """
    if usuario is None or not getattr(usuario, "is_authenticated", False):
        return ContextoDeAmbito(usuario_id=None, es_superusuario=False, ambitos=())

    if getattr(usuario, "is_superuser", False):
        # Superadmin: ambito global segun SPEC §5 (su gestion es por Django Admin,
        # pero tampoco puede quedar encerrado en el panel).
        return ContextoDeAmbito(
            usuario_id=usuario.pk, es_superusuario=True, ambitos=tuple()
        )

    # Import perezoso: evita dependencia circular apps.core -> apps.cuentas.
    from apps.cuentas.models import Membresia

    membresias = (
        Membresia.objects.filter(usuario=usuario, activa=True)
        .select_related("negocio", "sucursal")
        .only(
            "id",
            "negocio_id",
            "sucursal_id",
            "rol",
            "negocio__activo",
            "sucursal__activo",
        )
    )
    return ContextoDeAmbito(
        usuario_id=usuario.pk,
        es_superusuario=False,
        ambitos=_ambitos_desde_membresias(membresias),
    )


def recortar(queryset: QuerySet, usuario) -> QuerySet:
    """Recorta `queryset` al ambito del usuario.

    El superusuario (ambito global, segun SPEC §5) no se recorta.
    """
    contexto = con_ambito(usuario).contexto
    if contexto.es_superusuario:
        return queryset
    return queryset.filter(queryset.model.condicion_ambitos(contexto.ambitos))

