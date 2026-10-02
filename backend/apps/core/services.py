"""Utilidades tecnicas compartidas (sin reglas de negocio).

Solo helpers neutros que pueden usar varias apps: normalizacion de slugs y
validacion de zonas horarias. Nada aqui depende de una politica comercial.
"""
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.utils.text import slugify


def generar_slug(valor: str, max_length: int = 60) -> str:
    """Convierte un texto en un slug ASCII en minusculas.

    `slugify` ya elimina acentos y caracteres no ASCII, que es lo que exige la
    convencion de identificadores tecnicos del proyecto.
    """
    return slugify(valor or "")[:max_length].strip("-")


def zona_horaria_por_defecto() -> str:
    return getattr(settings, "DEFAULT_TIME_ZONE", "America/Argentina/Buenos_Aires")


def zona_horaria_valida(nombre: str) -> bool:
    if not nombre:
        return False
    try:
        ZoneInfo(nombre)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return False
    return True
