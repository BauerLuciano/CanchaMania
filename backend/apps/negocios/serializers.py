"""Serializers de negocios."""
from rest_framework import serializers

from apps.negocios.models import Negocio


class NegocioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Negocio
        fields = ["id", "nombre", "slug", "activo", "created_at", "updated_at"]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]
