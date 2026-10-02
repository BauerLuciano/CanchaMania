"""Rutas de autenticacion: `/api/auth/...` (SPEC §19)."""
from django.urls import path

from apps.cuentas import views

urlpatterns = [
    path("csrf/", views.CsrfView.as_view(), name="auth-csrf"),
    path("login/", views.LoginView.as_view(), name="auth-login"),
    path("logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("me/", views.PerfilView.as_view(), name="auth-me"),
    path("roles/", views.CatalogoRolesView.as_view(), name="auth-roles"),
]
