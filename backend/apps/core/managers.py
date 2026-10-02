"""Managers y querysets con aislamiento multi-tenant integrado.

`para_usuario(usuario)` recorta SIEMPRE el resultado segun las membresias activas
del usuario. Toda vista o servicio que necesite datos de un negocio debe pasar por
ahi: es el unico camino soportado, y por eso no puede olvidarse el filtro.

Esta disponible en los dos niveles a proposito:

    Negocio.objects.para_usuario(usuario)            # desde el manager
    Negocio.objects.filter(...).para_usuario(usuario)  # sobre un queryset

El segundo caso importa porque los viewsets parten de `get_queryset()`, que
devuelve un QuerySet: sin el metodo en el QuerySet, el aislamiento dependeria de
recordar cual de las dos formas usar.

El superusuario tiene ambito global (SPEC §5) y por eso no se recorta.
"""
from django.db import models

from apps.core.scoping import con_ambito, recortar


class ScopedQuerySet(models.QuerySet):
    """Queryset que sabe recortarse al ambito del usuario."""

    def para_usuario(self, usuario):
        return recortar(self, usuario)

    # Alias explicito, util para dejar clara la intencion en el codigo.
    for_usuario = para_usuario


class ScopedManager(models.Manager.from_queryset(ScopedQuerySet)):
    """Unico punto de entrada a los datos con ambito."""

    def para_usuario(self, usuario, queryset=None):
        base = self.get_queryset() if queryset is None else queryset
        return recortar(base, usuario)

    def ambito_de(self, usuario):
        """Ambitos del usuario, por si el consumidor necesita el detalle."""
        return con_ambito(usuario).contexto

    for_usuario = para_usuario
