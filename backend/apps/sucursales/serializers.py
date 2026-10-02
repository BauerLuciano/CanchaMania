"""Serializers de sucursales."""
from rest_framework import serializers

from apps.negocios.models import Negocio
from apps.sucursales.models import Sucursal


class SucursalSerializer(serializers.ModelSerializer):
    """Lectura y edicion de una sucursal.

    `negocio` es opcional y solo admite negocios que ya estan en el ambito del
    usuario: si no se manda, el backend lo deduce del ambito; si se manda uno
    ajeno, el serializer lo rechaza como valor invalido. En ningun caso el
    cliente decide el tenant: `services.py` vuelve a verificarlo.
    """

    negocio = serializers.PrimaryKeyRelatedField(
        queryset=Negocio.objects.all(),
        required=False,
        help_text="Opcional. Si se omite, se usa el negocio del ambito del usuario.",
    )
    negocio_nombre = serializers.CharField(source="negocio.nombre", read_only=True)

    class Meta:
        model = Sucursal
        fields = [
            "id",
            "negocio",
            "negocio_nombre",
            "nombre",
            "slug",
            "telefono",
            "direccion",
            "activo",
            "zona_horaria",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "negocio_nombre", "created_at", "updated_at"]
        extra_kwargs = {
            # Opcional en la entrada: si no viene, el servicio lo deriva del nombre.
            # En el modelo es obligatorio porque nunca queda vacio en la base.
            "slug": {"required": False},
        }
        # Sin validadores declarados. Al declararlos (aunque sea vacios) se apaga
        # el UniqueTogetherValidator que DRF genera desde `uniq_sucursal_slug_por_negocio`,
        # que ademas de comprobar la unicidad EXIGE que `negocio` y `slug` lleguen en
        # la peticion. Aqui no pueden exigirlo: los dos los resuelve `services.py`
        # desde el ambito y desde el nombre. La unicidad tambien se comprueba alli,
        # y ahi se reporta como 409 en vez de 400, que es el conflicto que de verdad
        # es (SPEC §19).
        validators = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._recortar_negocios()

    def _recortar_negocios(self):
        """Limita el campo `negocio` a los negocios del ambito del usuario."""
        usuario = self.context.get("usuario")
        campo = self.fields.get("negocio")
        if usuario is not None and campo is not None:
            campo.queryset = Negocio.objects.para_usuario(usuario)
