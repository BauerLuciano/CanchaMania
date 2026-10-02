"""Alta de un negocio con su Dueño y, opcionalmente, una sucursal.

Es la via soportada para el primer acceso al sistema, porque el alta de negocios no
tiene flujo definido en el SPEC (ni onboarding ni suscripción: §26 la deja
pendiente) y por eso la API de negocios es de solo lectura.

Uso:

    python manage.py crear_negocio \
        --nombre "Complejo Los Pinos" \
        --email dueno@lospinos.test \
        --contrasena "UnaClaveFuerte123" \
        --sucursal "Sucursal Apostoles"

La contraseña se pide de forma interactiva si se omite `--contrasena`, para que no
quede en el historial del shell.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.cuentas.roles import Rol
from apps.cuentas.services import crear_membresia, crear_usuario
from apps.negocios.services import crear_negocio


class Command(BaseCommand):
    help = "Crea un negocio, su Dueño y opcionalmente una sucursal inicial."

    def add_arguments(self, parser):
        parser.add_argument("--nombre", required=True, help="Nombre del negocio.")
        parser.add_argument("--slug", default=None, help="Slug publico (opcional).")
        parser.add_argument("--email", required=True, help="Email del Dueño (es su login).")
        parser.add_argument("--nombre-persona", default="", help="Nombre del Dueño.")
        parser.add_argument(
            "--contrasena",
            default=None,
            help="Contrasena del Dueño. Si se omite, se solicita de forma interactiva.",
        )
        parser.add_argument("--sucursal", default=None, help="Nombre de la sucursal inicial.")
        parser.add_argument("--slug-sucursal", default=None, help="Slug de la sucursal inicial.")

    def handle(self, *args, **opciones):
        contrasena = opciones["contrasena"]
        if not contrasena:
            contrasena = self._pedir_contrasena()
        if not contrasena:
            raise CommandError("La contrasena es obligatoria.")

        with transaction.atomic():
            negocio = crear_negocio(nombre=opciones["nombre"], slug=opciones["slug"])
            self.stdout.write(f"Negocio creado: {negocio.nombre} (slug={negocio.slug})")

            usuario = crear_usuario(
                email=opciones["email"],
                contrasena=contrasena,
                nombre=opciones["nombre_persona"] or opciones["nombre"],
            )
            self.stdout.write(f"Usuario creado: {usuario.email}")

            sucursal = None
            if opciones["sucursal"]:
                from apps.sucursales.models import Sucursal
                from apps.core.services import generar_slug

                sucursal = Sucursal.objects.create(
                    negocio=negocio,
                    nombre=opciones["sucursal"],
                    slug=generar_slug(opciones["slug_sucursal"] or opciones["sucursal"]),
                )
                self.stdout.write(f"Sucursal creada: {sucursal.nombre} (slug={sucursal.slug})")

            # El Dueño se crea sobre si mismo como operador: tiene el unico ambito.
            crear_membresia(
                usuario=usuario,
                rol=Rol.DUENO,
                usuario_creador=usuario,
                negocio_id=negocio.pk,
                sucursal_id=None,
            )
            self.stdout.write(f"Membresia {Rol.ETIQUETAS[Rol.DUENO]} creada.")

        self.stdout.write(self.style.SUCCESS("Listo. Puede iniciar sesion con ese email."))

    def _pedir_contrasena(self) -> str:
        from getpass import getpass

        contrasena = getpass("Contrasena del Dueno: ")
        confirmacion = getpass("Repita la contrasena: ")
        if contrasena != confirmacion:
            raise CommandError("Las contrasenas no coinciden.")
        return contrasena
