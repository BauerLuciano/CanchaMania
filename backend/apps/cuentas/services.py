"""Servicios de cuentas: sesion, ambito y permisos.

Toda la logica de negocio de esta app vive aca. Las vistas solo orquestan y los
serializers solo validan/transforman (SPEC §21).

Reglas criticas implementadas:

* el ambito se resuelve SIEMPRE desde el usuario y sus membresias activas;
* los permisos del panel son `model permissions` de Django, no un enum propio;
* el Dueño es la union de permisos de Encargado + Cajero;
* una membresia inactiva no otorga acceso alguno.
"""
from __future__ import annotations

import logging
from typing import Iterable

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import Permission
from django.db import IntegrityError, transaction

from apps.core.exceptions import (
    AmbitoInvalidoError,
    ConflictoError,
    CredencialesInvalidasError,
    SinAmbitoError,
)
from apps.core.scoping import Ambito, ContextoDeAmbito, con_ambito, resolver_ambito
from apps.cuentas.roles import Rol, permisos_de_rol

Usuario = get_user_model()

logger = logging.getLogger("apps.cuentas.auditoria")


# --- Autenticacion (sesion Django + CSRF, sin JWT) -------------------------


def iniciar_sesion(email, contrasena):
    """Autentica por email y contrasena.

    El mensaje de error es identico exista o no el email: no se revela si una
    cuenta esta registrada.
    """
    email = (email or "").strip().lower()
    usuario = authenticate(request=None, username=email, password=contrasena or "")
    if usuario is None or not usuario.is_active:
        raise CredencialesInvalidasError()
    return usuario


def perfil_de(usuario) -> dict:
    """Payload de `/api/auth/me/`: identidad, roles, ambitos y permisos.

    Los permisos los calcula el backend; el frontend solo los usa para mostrar u
    ocultar elementos. La autorizacion real ocurre en cada endpoint.
    """
    contexto = resolver_ambito(usuario)
    return {
        "id": usuario.pk,
        "email": usuario.email,
        "nombre": usuario.get_full_name(),
        "es_superadmin": bool(usuario.is_superuser),
        "roles": list(contexto.roles),
        "ambitos": [ambito_para_dict(a) for a in contexto.ambitos],
        "negocios": negocios_del_ambito(contexto),
        "sucursales": sucursales_del_ambito(contexto),
        "permisos": sorted(permisos_de_usuario(usuario)),
    }


def ambito_para_dict(ambito: Ambito) -> dict:
    return {
        "negocio_id": ambito.negocio_id,
        "sucursal_id": ambito.sucursal_id,
        "rol": ambito.rol,
        "ambito": "negocio" if ambito.es_todo_el_negocio else "sucursal",
    }


def negocios_del_ambito(contexto: ContextoDeAmbito) -> list[dict]:
    """Negocios visibles y su alcance, resueltos desde las membresias.

    No consulta la base: sale de las membresias activas del usuario.
    """
    por_negocio: dict[int, dict] = {}
    for ambito in contexto.ambitos:
        negocio = por_negocio.setdefault(
            ambito.negocio_id,
            {"todo_el_negocio": False, "roles": [], "sucursales": {}},
        )
        if ambito.sucursal_id is None:
            negocio["todo_el_negocio"] = True
        if ambito.rol and ambito.rol not in negocio["roles"]:
            negocio["roles"].append(ambito.rol)
        if ambito.sucursal_id is not None:
            sucursal = negocio["sucursales"].setdefault(ambito.sucursal_id, {"roles": []})
            if ambito.rol and ambito.rol not in sucursal["roles"]:
                sucursal["roles"].append(ambito.rol)

    resultado = []
    for negocio_id in sorted(por_negocio):
        datos = por_negocio[negocio_id]
        sucursales = [
            {"id": sucursal_id, "roles": sorted(datos["roles"])}
            for sucursal_id, datos in sorted(datos["sucursales"].items())
        ]
        resultado.append(
            {
                "id": negocio_id,
                "todo_el_negocio": datos["todo_el_negocio"],
                "roles": sorted(datos["roles"]),
                "sucursales": sucursales,
            }
        )
    return resultado


def sucursales_del_ambito(contexto: ContextoDeAmbito) -> list[dict]:
    """Sucursales con ambito acotado, aplanadas."""
    resultado = []
    for negocio in negocios_del_ambito(contexto):
        for sucursal in negocio["sucursales"]:
            resultado.append({**sucursal, "negocio_id": negocio["id"]})
    return resultado


# --- Permisos ---------------------------------------------------------------


def permisos_de_usuario(usuario) -> set[str]:
    """Permisos efectivos del usuario, como `app_label.codename`.

    Superusuario: todos los permisos existentes. Usuario normal: union de los
    permisos de los roles de sus membresias **activas**.

    Los codigos provienen del catalogo de `roles.py`, que los tests validan
    contra los permisos reales de Django: un error de tipeo se detecta en la
    suite, no en produccion.
    """
    if usuario is None or not getattr(usuario, "is_authenticated", False):
        return set()
    if usuario.is_superuser:
        return set(permisos_existentes())

    codigos: set[str] = set()
    for rol in resolver_ambito(usuario).roles:
        codigos |= permisos_de_rol(rol)
    return codigos


def permisos_existentes() -> set[str]:
    return {
        f"{p.content_type.app_label}.{p.codename}"
        for p in Permission.objects.select_related("content_type")
    }


def usuario_tiene_permiso(usuario, codigo: str) -> bool:
    """Verificacion real de permiso. La usa `apps.core.permissions.PermisoDeAccion`."""
    if not codigo:
        return False
    if usuario is None or not getattr(usuario, "is_authenticated", False):
        return False
    if usuario.is_superuser:
        return True
    return codigo in permisos_de_usuario(usuario)


def tiene_permisos(usuario, codigos: Iterable[str]) -> bool:
    """True solo si tiene TODOS los permisos indicados."""
    return all(usuario_tiene_permiso(usuario, codigo) for codigo in codigos)


# --- Ambito -----------------------------------------------------------------


def contexto_de(usuario) -> ContextoDeAmbito:
    return con_ambito(usuario).contexto


def exigir_ambito(usuario) -> ContextoDeAmbito:
    contexto = con_ambito(usuario).contexto
    if not contexto.tiene_ambito:
        raise SinAmbitoError()
    return contexto


def exigir_negocio(contexto: ContextoDeAmbito, negocio_id) -> int:
    """Valida que el negocio enviado pertenezca al ambito del usuario.

    Nunca se acepta un `negocio_id` sin verificarlo: si es ajeno se rechaza con
    403 AMBITO_INVALIDO y el recurso no se crea ni se mueve de ambito.
    """
    negocio_id = _a_id(negocio_id)
    if negocio_id is None:
        unico = contexto.unico_negocio_id()
        if unico is None:
            raise AmbitoInvalidoError(
                "Indique el negocio: el usuario tiene membresias en varios negocios.",
                codigo="NEGOCIO_AMBIGUO",
            )
        return unico
    if not contexto.negocio_cubierto(negocio_id):
        raise AmbitoInvalidoError()
    return negocio_id


def exigir_sucursal(contexto: ContextoDeAmbito, negocio_id, sucursal_id):
    """Valida que la sucursal enviada pertenezca al negocio y al ambito del usuario.

    El orden importa: primero se comprueba que la sucursal sea de ESTE negocio. Un
    ambito de negocio completo (Dueño) cubre todas las sucursales **de su
    negocio**, no las de los demas, asi que sin esta comprobacion un Dueño de A
    podria colar la sucursal de B.
    """
    from apps.sucursales.models import Sucursal  # import local: evita ciclo de modulo

    sucursal_id = _a_id(sucursal_id)
    if sucursal_id is None:
        return None
    if not Sucursal.objects.filter(pk=sucursal_id, negocio_id=negocio_id).exists():
        raise AmbitoInvalidoError(
            "La sucursal indicada no pertenece a su ambito.",
            codigo="SUCURSAL_FUERA_DE_AMBITO",
        )
    if not contexto.sucursal_abierta(negocio_id, sucursal_id):
        raise AmbitoInvalidoError(
            "La sucursal indicada no pertenece a su ambito.",
            codigo="SUCURSAL_FUERA_DE_AMBITO",
        )
    return sucursal_id


def _a_id(valor):
    """Normaliza a id lo que llega del cuerpo o de un serializer.

    Acepta `None`, un entero, un string numerico o el propio objeto ya resuelto
    por el serializer (`validated_data` trae instancias, no ids). En todos los
    casos el id devuelto es solo un candidato: la pertenencia al ambito la
    comprueban `exigir_negocio` y `exigir_sucursal`.
    """
    if valor is None or valor == "":
        return None
    if isinstance(valor, int):
        return valor
    clave = getattr(valor, "pk", None)
    if clave is not None:
        return int(clave)
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise AmbitoInvalidoError("Identificador invalido.", codigo="IDENTIFICADOR_INVALIDO")


# --- Usuarios y membresias --------------------------------------------------


@transaction.atomic
def crear_usuario(
    *,
    email,
    contrasena,
    nombre="",
    apellido="",
    telefono="",
    usuario_creador=None,
):
    """Crea un usuario interno nuevo. No crea membresias: eso es otra operacion.

    La membresia es la unica fuente de acceso, por lo que crear el usuario y
    darle permisos son dos pasos separados y auditables.
    """
    email = (email or "").strip().lower()
    if Usuario.objects.filter(email__iexact=email).exists():
        raise ConflictoError("Ya existe un usuario con ese email.", codigo="EMAIL_EN_USO")

    usuario = Usuario(
        email=email,
        first_name=nombre or "",
        last_name=apellido or "",
        telefono=telefono or "",
    )
    usuario.set_password(contrasena or "")
    usuario.save()

    if usuario_creador is not None:
        registrar_accion(
            actor=usuario_creador, accion="USUARIO_CREADO", detalle=f"usuario_id={usuario.pk}"
        )
    return usuario


@transaction.atomic
def crear_membresia(*, usuario, rol, usuario_creador=None, **alcance):
    """Crea una membresia validando rol, sucursal y ambito.

    El negocio y la sucursal se resuelven SIEMPRE contra el ambito de quien
    opera: un `sucursal_id` de otro negocio se rechaza, no se reasigna en
    silencio.
    """
    from apps.cuentas.models import Membresia  # import local: evita ciclo de modulo

    if rol not in Rol.TODOS:
        raise AmbitoInvalidoError("Rol desconocido.", codigo="ROL_INVALIDO")

    contexto = exigir_ambito(usuario_creador or usuario)
    negocio_id = exigir_negocio(contexto, alcance.get("negocio_id"))
    sucursal_id = exigir_sucursal(contexto, negocio_id, alcance.get("sucursal_id"))

    # El rol Dueño abarca TODO el negocio, asi que asignarlo es darle el control
    # completo del negocio. Por eso solo un Dueño (o el Superadmin) puede
    # entregarlo: un Encargado que puede crear membresias en su sucursal no puede
    # promover a nadie a Dueño, o su propia accion le daria mas permisos de los
    # que tiene.
    if rol == Rol.DUENO and not contexto.tiene_rol(Rol.DUENO):
        raise AmbitoInvalidoError(
            "Solo un Dueno puede asignar el rol Dueno.",
            codigo="ROL_NO_ASIGNABLE",
        )

    if Rol.REQUIERE_SUCURSAL[rol]:
        if sucursal_id is None:
            # Membresia de sucursal sin indicar cual: se resuelve solo si el
            # operador tiene un unico ambito de sucursal en ese negocio.
            candidatas = sorted(
                {
                    a.sucursal_id
                    for a in contexto.ambitos
                    if a.negocio_id == negocio_id and a.sucursal_id is not None
                }
            )
            if len(candidatas) != 1:
                raise AmbitoInvalidoError(
                    "Indique la sucursal para este rol.", codigo="SUCURSAL_REQUERIDA"
                )
            sucursal_id = candidatas[0]
    else:
        sucursal_id = None

    if Membresia.objects.filter(
        usuario=usuario, negocio_id=negocio_id, sucursal_id=sucursal_id, rol=rol
    ).exists():
        raise ConflictoError(
            "El usuario ya tiene una membresia con ese rol en ese ambito.",
            codigo="MEMBRESIA_DUPLICADA",
        )

    membresia = Membresia(
        usuario=usuario,
        negocio_id=negocio_id,
        sucursal_id=sucursal_id,
        rol=rol,
        activa=True,
    )
    try:
        # full_clean ejecuta `clean()` (rol <-> sucursal, sucursal del negocio) y
        # `validate_constraints()` (los UniqueConstraint condicionales de Meta).
        membresia.full_clean()
        membresia.save()
    except IntegrityError as exc:
        # Backstop contra carreras: las constraints de PostgreSQL son la verdad.
        raise ConflictoError(
            "El usuario ya tiene una membresia con ese rol en ese ambito.",
            codigo="MEMBRESIA_DUPLICADA",
        ) from exc

    if usuario_creador is not None:
        registrar_accion(
            actor=usuario_creador,
            accion="MEMBRESIA_CREADA",
            detalle=(
                f"usuario_id={usuario.pk} rol={rol} "
                f"negocio_id={negocio_id} sucursal_id={sucursal_id}"
            ),
        )
    return membresia


@transaction.atomic
def crear_dueno_de_origen(*, usuario, negocio):
    """Alta de origen: el Dueño del primer negocio, que aun no tiene a nadie.

    Es la UNICA via para dar membresia a alguien que todavia no tiene ninguna, y
    existe solo para el arranque del sistema (el comando `crear_negocio`), donde
    la chicken-and-egg es real: el primer Dueno no puede tener ambito porque no
    hay ningun Dueno que se lo pueda dar. `crear_membresia` resuelve el ambito
    contra quien opera, asi que en el arranque no hay contra quien resolverlo.

    No la llama ninguna vista ni serializer: la API nunca la alcanza. Es una via
    de consola, no una puerta trasera de la API.

    Garantias, y por eso no es un atajo para ampliar permisos:

    * el rol es SIEMPRE `DUENO` sobre todo el negocio, sin opcion a parametrizar;
    * el usuario no puede tener NINGUNA membresia previa (activa o no), asi que
      no sirve para colar permisos extra a alguien que ya accede al sistema;
    * el negocio no puede tener ninguna membresia activa, asi que no sirve para
      colar un segundo Dueno al lado del Dueno real.

    Todo lo demas sigue igual que en `crear_membresia`: `full_clean()` ejecuta
    `clean()` y las constraints, y la `IntegrityError` de PostgreSQL es el
    backstop final contra carreras.
    """
    from apps.cuentas.models import Membresia  # import local: evita ciclo de modulo

    if Membresia.objects.filter(usuario_id=usuario.pk).exists():
        raise ConflictoError(
            "El usuario ya tiene membresias:Amplie sus permisos desde el panel.",
            codigo="MEMBRESIA_DUPLICADA",
        )

    if Membresia.objects.filter(negocio_id=negocio.pk, activa=True).exists():
        raise ConflictoError(
            "El negocio ya tiene membresias: Amplie sus permisos desde el panel.",
            codigo="MEMBRESIA_DUPLICADA",
        )

    membresia = Membresia(
        usuario=usuario,
        negocio_id=negocio.pk,
        sucursal_id=None,
        rol=Rol.DUENO,
        activa=True,
    )
    try:
        # Mismo motivo que en `crear_membresia`: `full_clean()` corre `clean()`
        # (rol <-> sucursal) y `validate_constraints()`.
        membresia.full_clean()
        membresia.save()
    except IntegrityError as exc:
        # Backstop contra carreras: las constraints de PostgreSQL son la verdad.
        raise ConflictoError(
            "El negocio ya tiene un Dueno.", codigo="MEMBRESIA_DUPLICADA"
        ) from exc

    registrar_accion(
        actor=usuario,
        accion="DUENO_ORIGEN_CREADO",
        detalle=f"usuario_id={usuario.pk} negocio_id={negocio.pk}",
    )
    return membresia


def desactivar_membresia(membresia, usuario_operador):
    """Da de baja una membresia. No se borra: queda el rastro (SPEC §17)."""
    from apps.cuentas.models import Membresia

    if not Membresia.objects.para_usuario(usuario_operador).filter(pk=membresia.pk).exists():
        raise AmbitoInvalidoError()

    # Como en `desactivar_usuario`: quitarse el acceso desde la propia pantalla
    # dejaria al operador sin poder entrar al panel, y el error se descubriria
    # recien en el proximo login.
    if membresia.usuario_id == usuario_operador.pk:
        raise AmbitoInvalidoError(
            "No puede desactivar su propia membresia.", codigo="AUTODEACTIVACION"
        )

    membresia.activa = False
    membresia.save(update_fields=["activa", "updated_at"])
    registrar_accion(
        actor=usuario_operador,
        accion="MEMBRESIA_DESACTIVADA",
        detalle=f"membresia_id={membresia.pk} usuario_id={membresia.usuario_id}",
    )
    return membresia


def desactivar_usuario(usuario_objetivo, usuario_operador):
    """Baja logica de un usuario, siempre dentro del ambito del operador."""
    exigir_usuario_alcanzable(usuario_objetivo.pk, usuario_operador)

    if usuario_objetivo.pk == usuario_operador.pk:
        raise AmbitoInvalidoError(
            "No puede desactivar su propio usuario.", codigo="AUTODEACTIVACION"
        )

    usuario_objetivo.is_active = False
    usuario_objetivo.save(update_fields=["is_active", "actualizado_en"])
    registrar_accion(
        actor=usuario_operador,
        accion="USUARIO_DESACTIVADO",
        detalle=f"usuario_id={usuario_objetivo.pk}",
    )
    return usuario_objetivo


def exigir_usuario_alcanzable(usuario_id, usuario_operador):
    """Resuelve el usuario destino de una membresia o de una baja, si es alcanzable.

    Alcanzable significa una de dos cosas:

    * el operador lo ve en su ambito, porque tiene alguna membresia dentro; o
    * el usuario no tiene ninguna membresia todavia, que es el recien creado.

    El segundo caso es necesario: si solo se aceptara el primero, el alta de
    personal quedaria trabada, porque al crear el usuario todavia no tiene
    membresias y por eso nadie podria asignarle la primera.

    Un usuario cuyas membresias estan todas fuera del ambito del operador NO es
    alcanzable aunque se conozca su ID: pertenece a otro negocio.
    """
    from apps.cuentas.models import Membresia

    if Membresia.objects.filter(usuario_id=usuario_id).exists():
        visible = (
            Membresia.objects.para_usuario(usuario_operador)
            .filter(usuario_id=usuario_id)
            .exists()
        )
        if not visible:
            raise AmbitoInvalidoError(
                "El usuario indicado no pertenece a su ambito.",
                codigo="USUARIO_FUERA_DE_AMBITO",
            )
    return Usuario.objects.get(pk=usuario_id)


def registrar_accion(*, actor, accion, detalle=""):
    """Auditoria minima de la Etapa 1 (SPEC §17).

    Cuando exista el modelo de auditoria de una etapa posterior, este es el unico
    punto que hay que cambiar.
    """
    logger.info("accion=%s actor=%s detalle=%s", accion, getattr(actor, "pk", None), detalle)
