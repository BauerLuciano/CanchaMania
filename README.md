# CanchaMania

Sistema de gestión para complejos de canchas.

La especificación funcional y arquitectónica completa vive en [`SPEC.md`](SPEC.md).
Este README documenta cómo se levanta el proyecto y qué incluye la Etapa 1.

---

## Estado actual: Etapa 1 (backend)

Está implementado **solo el backend** del Stage 1. **No hay frontend todavía.**

Alcance entregado:

- Modelo de datos inicial: `Negocio`, `Sucursal`, `Usuario`, `Membresia` (SPEC §18).
- Autenticación por sesión Django con CSRF obligatorio, incluso en el login.
- Multi-tenancy: todo acceso se recorta al ámbito del usuario y sus membresías activas.
- Permisos por rol (`DUENO`, `ENCARGADO`, `CAJERO`) sobre los *model permissions* de Django.
- API de negocios (solo lectura), sucursales, usuarios y membresías.

No implementado todavía, a propósito: reservas, pagos, Mercado Pago, canchas,
canchas/franjas, clientes, ventas, caja, reportes y configuración. Esos módulos
entran en las etapas siguientes del SPEC §23.

---

## Requisitos

- Python 3.13
- PostgreSQL 17 (o superior)
- Node 22+ (solo cuando exista el frontend)

---

## Puesta en marcha

### 1. Entorno de Python

Desde la raíz del proyecto:

```bash
python -m venv .venv
.venv\Scripts\pip install -r backend\requirements.txt
```

### 2. Configuración

El backend lee sus variables de `backend/.env`, que **nunca se versiona**.
La plantilla está en `backend/.env.example`:

```bash
cp backend/.env.example backend/.env
```

Generá la clave secreta que pide el ejemplo:

```bash
.venv\Scripts\python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

### 3. Base de datos

Creá la base que figure en `DATABASE_NAME` y corré las migraciones:

```bash
.venv\Scripts\python backend\manage.py migrate
```

### 4. Primer negocio

En la Etapa 1 los negocios se dan de alta por comando de administración
(no hay alta por API porque el SPEC no define ese flujo):

```bash
.venv\Scripts\python backend\manage.py crear_negocio \
    --nombre "Complejo Los Pinos" \
    --email dueno@canchamania.test \
    --sucursal "Sucursal Apóstoles"
```

Sin `--contrasena` la clave se pide de forma interactiva, para que no quede en el
historial del shell. `crear_negocio --help` lista el resto de las opciones.

### 5. Levantar

```bash
.venv\Scripts\python backend\manage.py runserver
```

El panel administrativo global (Superadmin) queda en `/admin/`.

---

## Comandos

| Comando | Qué hace |
| --- | --- |
| `python backend\manage.py check` | Verificación de configuración de Django. |
| `python backend\manage.py migrate` | Aplica las migraciones. |
| `python backend\manage.py makemigrations` | Genera migraciones tras cambiar modelos. |
| `python backend\manage.py runserver` | Servidor de desarrollo. |
| `python backend\manage.py test` | No usar: la suite corre con pytest. |
| `python backend\manage.py crear_negocio --help` | Alta de negocio con su Dueño. |

## Tests

Los tests corren contra **PostgreSQL**, nunca contra SQLite: Django crea y borra
la base `DATABASE_TEST_NAME` (por defecto `test_canchamania`) en cada sesión.

```bash
cd backend
..\.venv\Scripts\python -m pytest -q
```

---

## Estructura

```text
CanchaMania/
├── SPEC.md                  Especificación. No se modifica.
├── README.md
├── backend/
│   ├── manage.py
│   ├── pytest.ini
│   ├── requirements.txt
│   ├── .env.example
│   ├── config/              settings, urls raíz, wsgi/asgi
│   └── apps/
│       ├── core/            Base compartida: scoping, permisos, errores, managers
│       ├── cuentas/         Usuario, Membresia, sesión, roles
│       ├── negocios/        Negocio
│       └── sucursales/      Sucursal
└── frontend/                (Etapa 2)
```

`apps/core` concentra lo transversal: `TenantScopedModel` resuelve la condición
SQL de ámbito de cada modelo, `ScopedManager.para_usuario(...)` es el único punto
de entrada a datos permitidos, y `BaseScopedViewSet` + `PermisoDeAccion` aseguran
que ningún endpoint olvide el recorte ni el permiso.

La regla de oro: **el backend es la autoridad del permiso y del ámbito**. El
frontend usa la lista de permisos que devuelve `/api/auth/me/` solo para ocultar
pantallas.

---

## API

Prefijo `/api/`. Formato uniforme de error:

```json
{ "codigo": "...", "mensaje": "...", "detalles": { "campo": "..." } }
```

### Sesión

| Método | Ruta | Qué hace |
| --- | --- | --- |
| `GET` | `/api/auth/csrf/` | Entrega la cookie y el token CSRF. |
| `POST` | `/api/auth/login/` | Login por email. |
| `POST` | `/api/auth/logout/` | Cierra la sesión. |
| `GET` | `/api/auth/me/` | Identidad, roles, ámbitos y permisos del usuario. |
| `GET` | `/api/auth/roles/` | Catálogo de roles. |

### Panel

| Método | Ruta | Permiso |
| --- | --- | --- |
| `GET` | `/api/negocios/`, `/api/negocios/<id>/` | `negocios.view_negocio` |
| `GET/POST/PATCH/DELETE` | `/api/sucursales/` | `sucursales.{view,add,change,delete}_sucursal` |
| `GET/POST/PATCH` | `/api/usuarios/` | `cuentas.{view,add,change}_usuario` |
| `POST` | `/api/usuarios/<id>/desactivar/` | `cuentas.change_usuario` |
| `GET/POST/DELETE` | `/api/membresias/` | `cuentas.{view,add,change}_membresia` |

Los usuarios no se borran: `DELETE /api/usuarios/<id>/` responde `405` y la baja
lógica va por `desactivar`. En membresías, `DELETE` es una baja lógica también.

### Códigos de error que el frontend debe diferenciar

| Código | HTTP | Significado |
| --- | --- | --- |
| `NO_AUTENTICADO` | 401 | Sesión ausente o caducada. |
| `CSRF_INVALIDO` | 403 | Falta o no cuadra el token CSRF. |
| `SIN_PERMISOS` | 403 | El rol no alcanza para la acción. |
| `SIN_AMBITO` | 403 | El usuario no tiene ninguna membresía activa. |
| `AMBITO_INVALIDO` | 403 | El recurso o el id enviado quedan fuera del ámbito. |
| `VALIDACION_INVALIDA` | 400 | Campo inválido; el detalle va en `detalles`. |
| `CONFLICTO` | 409 | El recurso ya existe o tiene datos asociados. |
| `NO_ENCONTRADO` | 404 | El recurso no existe **o** está fuera del ámbito. |

Sobre el 404: un recurso de otro negocio devuelve 404 y no 403, para no confirmar
que exista. En cambio, si el rol no tiene el permiso de la acción, la respuesta
es 403 — la misma que se recibiría con un recurso propio, así que tampoco filtra.

---

## Seguridad (SPEC §22)

- Sin JWT: sesión Django con cookie y CSRF obligatorio en toda escritura.
- Sin CORS: frontend y API bajo el mismo dominio. En desarrollo el proxy lo hace
  Vite; en producción Django sirve el build con WhiteNoise.
- `is_superuser` es el único bypass de ámbito. `is_staff` no lo es.
- CSRF nunca se desactiva, ni en el login: el token se pide antes de escribir.
- `.env` jamás se versiona. Los secretos llegan por variables de entorno.

---

## Decisiones de la Etapa 1

- **Membresía**: `usuario + negocio + sucursal(opcional) + rol + activa`.
  `sucursal = NULL` significa Dueño y da acceso a todo el negocio;
  `sucursal = X` significa Encargado o Cajero y da acceso a esa sede.
  La cancha **no** forma parte de la membresía.
- **Recurso fuera de ámbito → 404**, para no confirmar su existencia.
- **Baja de sucursal y de membresía**: `PROTECT` en las claves ajenas. Si hay
  datos colgados se rechaza y la salida recomendada es desactivar.
- **Alta de negocio**: solo por comando o Django Admin, porque el SPEC no define
  el flujo comercial de alta.
- **Regla `(negocio, slug)` única de sucursal**: la vigila `services.py`, no el
  serializer, porque su consecuencia correcta es un 409 y no un 400 de formulario.
- **Rol `DUENO`**: solo un Dueño puede asignarlo, porque amplía el alcance a todo
  el negocio y sería un autoescalamiento de privilegios.