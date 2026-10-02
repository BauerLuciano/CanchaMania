"""Administracion de sucursales (Superadmin, SPEC §5)."""
from django.contrib import admin

from apps.sucursales.models import Sucursal


@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ("nombre", "negocio", "slug", "activo", "zona_horaria", "created_at")
    list_filter = ("activo", "negocio")
    search_fields = ("nombre", "slug", "direccion")
    ordering = ("negocio", "nombre")
    readonly_fields = ("created_at", "updated_at")
    fields = (
        "negocio",
        "nombre",
        "slug",
        "telefono",
        "direccion",
        "activo",
        "zona_horaria",
    )
