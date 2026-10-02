"""Serializers de cuentas.

Los serializers solo validan y transforman. Toda decision de negocio
(que negocio, que sucursal, si el rol es valido) vive en `services.py`.
"""
from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.cuentas.models import Membresia
from apps.cuentas.roles import Rol
from apps.negocios.models import Negocio
from apps.sucursales.models import Sucursal

Usuario = get_user_model()


class UsuarioSerializer(serializers.ModelSerializer):
    """Vista de un usuario dentro del panel."""

    nombre = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = Usuario
        fields = ["id", "email", "nombre", "first_name", "last_name", "telefono", "is_active"]
        read_only_fields = ["id", "email", "is_active"]


class UsuarioCrearSerializer(serializers.Serializer):
    """Alta de usuario. La contrasena es de escritura y nunca se devuelve."""

    email = serializers.EmailField()
    contrasena = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)
    nombre = serializers.CharField(required=False, allow_blank=True, max_length=150)
    apellido = serializers.CharField(required=False, allow_blank=True, max_length=150)
    telefono = serializers.CharField(required=False, allow_blank=True, max_length=32)


class UsuarioActualizacionSerializer(serializers.Serializer):
    """Edicion de datos de contacto.

    `email` e `is_active` NO son editables aca: el email es la identidad de acceso
    y la baja es logica y pasa por `desactivar`, que impide la autoactivacion.

    `nombre` y `apellido` mapean a `first_name` / `last_name` por `source`, asi
    que el nombre del campo es el de la API y el del atributo sigue siendo el del
    modelo.
    """

    nombre = serializers.CharField(
        source="first_name", required=False, allow_blank=True, max_length=150
    )
    apellido = serializers.CharField(
        source="last_name", required=False, allow_blank=True, max_length=150
    )
    telefono = serializers.CharField(required=False, allow_blank=True, max_length=32)

    def update(self, instancia, datos_validados):
        """Aplica los campos al usuario.

        `validated_data` ya viene con los nombres del modelo (gracias al `source`),
        asi que alcanza con asignar y guardar. Solo llega lo que este serializer
        expone: `email` e `is_active` no son editables por esta via.
        """
        for atributo, valor in datos_validados.items():
            setattr(instancia, atributo, valor)
        instancia.save()
        return instancia


class MembresiaSerializer(serializers.ModelSerializer):
    usuario_email = serializers.EmailField(source="usuario.email", read_only=True)
    negocio_nombre = serializers.CharField(source="negocio.nombre", read_only=True)
    sucursal_nombre = serializers.CharField(source="sucursal.nombre", read_only=True, default=None)

    class Meta:
        model = Membresia
        fields = [
            "id",
            "usuario",
            "usuario_email",
            "negocio",
            "negocio_nombre",
            "sucursal",
            "sucursal_nombre",
            "rol",
            "activa",
        ]
        read_only_fields = ["id", "usuario_email", "negocio_nombre", "sucursal_nombre"]


class MembresiaCrearSerializer(serializers.Serializer):
    """Alta de membresia.

    `negocio_id` y `sucursal_id` se reciben con esos nombres porque son las claves
    que expone la API, pero NO son enteros libres: son campos de relacion cuyo
    queryset ya viene recortado al ambito del operador. Un id ajeno no llega
    siquiera a ser una opcion valida, y la respuesta es de campo invalido (400),
    igual que el campo `negocio` de las sucursales. Un 403 queda para lo que no
    es una eleccion del formulario (SPEC §19).

    La comprobacion definitiva sigue estando en `services.py`: el serializer no
    es la autoridad del ambito, solo evita ofrecer lo que no corresponde.
    """

    usuario = serializers.IntegerField()
    rol = serializers.ChoiceField(choices=list(Rol.TODOS))
    negocio_id = serializers.PrimaryKeyRelatedField(
        source="negocio",
        # Queryset base sin recortar: `__init__` lo deja en el ambito del operador
        # antes de que se use. DRF exige uno en la declaracion, asi que se declara
        # el mas amplio y se acota despues.
        queryset=Negocio.objects.all(),
        required=False,
        allow_null=True,
    )
    sucursal_id = serializers.PrimaryKeyRelatedField(
        source="sucursal",
        queryset=Sucursal.objects.all(),
        required=False,
        allow_null=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._recortar_ambito()

    def _recortar_ambito(self):
        """Ofrece solo negocios y sucursales que ya estan en el ambito."""
        usuario = self.context.get("usuario")
        if usuario is None:
            return
        self.fields["negocio_id"].queryset = Negocio.objects.para_usuario(usuario)
        self.fields["sucursal_id"].queryset = Sucursal.objects.para_usuario(usuario)
