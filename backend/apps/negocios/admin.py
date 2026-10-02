"""Administracion de negocios (Superadmin, SPEC §5)."""
from django.contrib import admin

from apps.negocios.models import Negocio


@admin.register(Negocio)
class NegocioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "slug", "activo", "created_at")
    list_filter = ("activo",)
    search_fields = ("nombre", "slug")
    prepopulated_fields = {"slug": ("nombre",)}
    ordering = ("nombre",)
    readonly_fields = ("created_at", "updated_at")
