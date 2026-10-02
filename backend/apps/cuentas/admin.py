"""Administracion de cuentas y membresias (Superadmin, SPEC §5).

Tambien es la via soportada para dar de alta negocios con su Dueño en la Etapa 1,
porque la API de negocios es de solo lectura (ver README).
"""
from django.contrib import admin

from apps.cuentas.models import Membresia, Usuario


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ("email", "first_name", "last_name", "is_active", "is_staff", "creado_en")
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)
    filter_horizontal = ("groups", "user_permissions")
    readonly_fields = ("creado_en", "actualizado_en", "last_login")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos", {"fields": ("first_name", "last_name", "telefono")}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Fechas", {"fields": ("last_login", "creado_en", "actualizado_en")}),
    )

    def has_add_permission(self, request):
        # El alta de usuarios se hace por password hasheado, no desde el admin.
        return False


@admin.register(Membresia)
class MembresiaAdmin(admin.ModelAdmin):
    list_display = ("usuario", "negocio", "sucursal", "rol", "activa", "created_at")
    list_filter = ("rol", "activa", "negocio")
    search_fields = ("usuario__email", "negocio__nombre", "sucursal__nombre")
    autocomplete_fields = ("usuario",)
    ordering = ("negocio", "sucursal", "rol")

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        # Que la sucursal solo ofrezca las del negocio elegido.
        if db_field.name == "sucursal" and "negocio" in request.GET:
            kwargs["queryset"] = self._sucursales_de(request.GET.get("negocio"))
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    @staticmethod
    def _sucursales_de(negocio_id):
        from apps.sucursales.models import Sucursal

        try:
            return Sucursal.objects.filter(negocio_id=int(negocio_id))
        except (TypeError, ValueError):
            return Sucursal.objects.none()
