"""Catalogo de roles y mapa rol -> permisos (SPEC §5).

Este archivo contiene **dato tecnico editable**, no una regla comercial:

* los roles son los tres definidos por el SPEC (DUENO, ENCARGADO, CAJERO);
* los permisos son los `model permissions` de Django, no un enum propio, para que
  admin, auditoria y tests usen el mismo mecanismo;
* el Dueño es la UNION de Encargado + Cajero, sin jerarquías ni hacks.

El Superadmin no aparece aca: administra globalmente por Django Admin.
"""
from __future__ import annotations

from django.db.models import Q


class Rol:
    DUENO = "DUENO"
    ENCARGADO = "ENCARGADO"
    CAJERO = "CAJERO"

    TODOS = (DUENO, ENCARGADO, CAJERO)

    #: Etiquetas legibles para la interfaz.
    ETIQUETAS = {
        DUENO: "Dueno",
        ENCARGADO: "Encargado",
        CAJERO: "Cajero",
    }

    #: La membresia de un Dueño es sobre todo el negocio (sin sucursal).
    #: Encargado y Cajero son siempre sobre una sucursal concreta.
    REQUIERE_SUCURSAL = {DUENO: False, ENCARGADO: True, CAJERO: True}


# --- Permisos por rol ------------------------------------------------------
# Se referencian permisos que Django crea solo: `app_label.codename`.
# Los roles de etapas posteriores sumaran sus permisos aqui.

_PERMISOS_ENCARGADO = (
    "negocios.view_negocio",
    "sucursales.view_sucursal",
    "sucursales.add_sucursal",
    "sucursales.change_sucursal",
    "cuentas.view_usuario",
    "cuentas.view_membresia",
    "cuentas.add_membresia",
    "cuentas.change_membresia",
)

_PERMISOS_CAJERO = (
    "negocios.view_negocio",
    "sucursales.view_sucursal",
    "cuentas.view_usuario",
)

# El Dueño administra por completo el negocio, incluido el alta y la baja de
# sucursales, de usuarios y de membresias. El borrado de un negocio completo no
# se expone por API: el alta de negocios se hace por Django Admin (ver README).
_PERMISOS_EXCLUSIVOS_DUENO = (
    "sucursales.delete_sucursal",
    "cuentas.add_usuario",
    "cuentas.change_usuario",
    "cuentas.delete_membresia",
)

PERMISOS_POR_ROL: dict[str, frozenset[str]] = {
    Rol.ENCARGADO: frozenset(_PERMISOS_ENCARGADO),
    Rol.CAJERO: frozenset(_PERMISOS_CAJERO),
    # Union, no copia: la definicion del Dueño deriva de los otros dos roles.
    Rol.DUENO: (
        frozenset(_PERMISOS_ENCARGADO)
        | frozenset(_PERMISOS_CAJERO)
        | frozenset(_PERMISOS_EXCLUSIVOS_DUENO)
    ),
}


def permisos_de_rol(rol: str) -> frozenset[str]:
    """Permisos efectivos del rol, o conjunto vacio si el rol no existe."""
    return PERMISOS_POR_ROL.get(rol, frozenset())


def es_rol_valido(rol) -> bool:
    return rol in Rol.TODOS


def roles_disponibles() -> list[dict]:
    """Catalogo serializable para el frontend."""
    return [
        {
            "valor": rol,
            "etiqueta": Rol.ETIQUETAS[rol],
            "requiere_sucursal": Rol.REQUIERE_SUCURSAL[rol],
            "ambito": "negocio" if not Rol.REQUIERE_SUCURSAL[rol] else "sucursal",
        }
        for rol in Rol.TODOS
    ]


def filtro_permisos(permisos) -> Q:
    """Q para filtrar permisos de Django por codenames `app_label.codename`."""
    condiciones = Q()
    for codigo in permisos:
        app_label, _, codename = codigo.partition(".")
        if codename:
            condiciones |= Q(codename=codename, content_type__app_label=app_label)
    return condiciones
