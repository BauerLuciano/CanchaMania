# SPEC: CanchaMania — Sistema de gestión para complejos de canchas

> Documento de referencia para OpenCode. Leerlo completo antes de escribir código.
>
> Si una decisión de negocio cambia, **actualizar este documento primero y después modificar el código**.
>
> **Regla principal:** no asumir reglas comerciales que no estén definidas. Todo comportamiento que dependa de la política de cada negocio debe ser parametrizable cuando corresponda.

---

## 1. Resumen

CanchaMania es un sistema web multi-tenant para la gestión de negocios dedicados principalmente a complejos de fútbol 5.

El sistema permite administrar:

* sucursales/complejos;
* canchas y horarios;
* reservas online y manuales;
* grupos fijos;
* clientes;
* pagos;
* Mercado Pago;
* buffet y ventas;
* stock;
* caja;
* usuarios y permisos;
* reportes.

### Estructura organizacional

Un negocio puede tener una o varias sucursales:

```text
NEGOCIO
├── Sucursal / Complejo Centro
├── Sucursal / Complejo Norte
└── Sucursal / Complejo Posadas
```

Cada sucursal administra sus propias:

* canchas;
* horarios;
* reservas;
* clientes;
* caja;
* ventas;
* stock;
* configuración operativa.

El negocio puede utilizar una misma cuenta de Mercado Pago para sus distintas sucursales.

CanchaMania **no recibe ni intermedia los fondos** de los negocios. Cada negocio conecta su propia cuenta de Mercado Pago.

Contexto inicial:

* Argentina.
* Moneda ARS.
* Zona horaria `America/Argentina/Buenos_Aires`.
* Idioma español.

---

# 2. Alcance

## 2.1 Entra en el MVP

* Gestión de negocios y múltiples sucursales.
* Usuarios y permisos por negocio/sucursal.
* Grilla de turnos por cancha y horario.
* Reservas online.
* Pago obligatorio para confirmar reservas online.
* Mercado Pago Checkout Pro.
* Webhook de Mercado Pago.
* Reservas manuales desde el panel.
* Pagos parciales y múltiples pagos por reserva.
* Múltiples medios de pago para una misma reserva.
* Cancelaciones y cálculo de devolución.
* Registro manual de devoluciones.
* No-show.
* Deudas derivadas de no-show según configuración.
* Bloqueo de nuevas reservas por deuda según configuración.
* Extensión de reservas.
* Grupos fijos.
* Clientes.
* Cantidad de jugadores por reserva.
* Jugadores genéricos con nombre opcional.
* Configuración del precio según cantidad de jugadores.
* ABM de productos y categorías.
* Stock simple.
* Venta rápida / punto de venta.
* Cuenta de consumo asociada a una reserva.
* Caja por sucursal.
* Apertura, movimientos y cierre con arqueo.
* Reportes básicos.
* Avisos por WhatsApp en etapa final.

## 2.2 NO entra en el MVP

* Facturación electrónica / ARCA.
* Tickets fiscales.
* Marketplace de búsqueda de canchas.
* Perfiles públicos de jugadores.
* Torneos.
* Rankings.
* Armado de equipos.
* App móvil nativa.
* Pádel u otros deportes como funcionalidad operativa.
* Proveedores.
* Recetas.
* Combos complejos.
* Intermediación de dinero de los negocios.
* Integración bancaria directa.
* Cobro automático de la suscripción de CanchaMania.

---

# 3. Stack

## Backend

* Python.
* Django.
* Django REST Framework.
* PostgreSQL.
* Autenticación mediante sesión Django + cookie + CSRF.
* Frontend y API bajo el mismo dominio.
* Tareas programadas mediante management commands + cron.
* Celery solamente si posteriormente resulta necesario.
* SDK oficial de Mercado Pago para Python.

## Frontend

* Vue 3.
* Composition API.
* `<script setup>`.
* Vite.
* Vue Router.
* Pinia.
* Tailwind CSS.
* Cliente HTTP único en `src/api/client.js`.

## Hosting

Railway, Render o VPS.

Secretos mediante variables de entorno.

Nunca guardar secretos en el repositorio.

---

# 4. Multi-tenancy, negocio y sucursales

## 4.1 Negocio

Representa al cliente de CanchaMania.

Un negocio puede tener una o varias sucursales.

Ejemplo:

```text
Negocio: Complejo Los Pinos

├── Sucursal Apóstoles
│   ├── Cancha 1
│   ├── Cancha 2
│   └── Caja
│
└── Sucursal Posadas
    ├── Cancha 1
    ├── Cancha 2
    └── Caja
```

## 4.2 Sucursal / Complejo

Cada sucursal tiene su propia operación.

Debe poder configurar de manera independiente:

* nombre;
* dirección;
* teléfono;
* horarios;
* días de atención;
* canchas;
* precios;
* reglas de reservas;
* políticas de cancelación;
* políticas de no-show;
* configuración operativa.

La misma numeración de cancha puede existir en distintas sucursales.

La interfaz pública debe identificar claramente la sucursal para evitar confusiones.

Ejemplo:

```text
Cancha 3
Av. Juan Román Riquelme 123
```

Una sucursal cerrada no debe mostrar horarios disponibles para reservar.

## 4.3 Mercado Pago

La integración de Mercado Pago pertenece al **negocio**, no a cada cancha.

Un negocio puede utilizar la misma cuenta de Mercado Pago para sus distintas sucursales.

CanchaMania no intermedia los fondos.

Las credenciales del negocio deben almacenarse de forma segura y nunca exponerse al frontend.

---

# 5. Roles y permisos

Roles dentro de un negocio/sucursal:

| Rol        | Alcance                                           |
| ---------- | ------------------------------------------------- |
| Superadmin | Administración global mediante Django Admin       |
| Dueño      | Administración completa del negocio               |
| Encargado  | Operación del negocio según permisos              |
| Cajero     | Operación de caja, cobros y ventas según permisos |

El cliente final **no necesita una cuenta** para reservar.

## Reglas

Un usuario se vincula mediante una membresía.

Un mismo usuario puede pertenecer a varios negocios/sucursales según el modelo de membresías aprobado.

El Dueño hereda los permisos operativos del Encargado y Cajero.

Los permisos reales siempre se validan en backend.

El frontend solamente controla visibilidad.

## Regla de seguridad crítica

Toda consulta autenticada debe estar limitada al ámbito autorizado del usuario.

Un usuario nunca puede consultar ni modificar información de otro negocio/sucursal manipulando IDs.

Debe existir cobertura de tests de aislamiento multi-tenant.

---

# 6. Regla de parametrización

**No hardcodear reglas comerciales que puedan depender de cada negocio.**

Ejemplos de valores que deben ser configurables:

* porcentaje de seña;
* monto de seña;
* ventana de cancelación;
* política de devolución;
* horarios;
* días de atención;
* duración de turnos;
* precios;
* duración de extensiones;
* política de no-show;
* generación de deuda;
* bloqueo por deuda;
* forma de cálculo del precio según jugadores;
* cantidad de jugadores;
* políticas de grupos fijos;
* anticipación de avisos;
* demás reglas comerciales que se incorporen.

Los valores iniciales pueden existir como **valores por defecto de configuración**, pero nunca deben convertirse en constantes rígidas del sistema.

---

# 7. Reservas

## 7.1 Estados

Los estados principales de una reserva son:

```text
CONFIRMADA
EN_CURSO
FINALIZADA
CANCELADA
NO_ASISTIO
```

No utilizar:

* `pendiente_pago`;
* `expirada`.

Una operación técnica de pago pendiente **no es una reserva confirmada**.

## 7.2 Reserva online

La reserva online requiere pago.

Flujo:

```text
Cliente selecciona horario
        ↓
Ingresa sus datos
        ↓
Selecciona forma de pago de la reserva
        ↓
Realiza el pago requerido
        ↓
Mercado Pago confirma
        ↓
Se crea/confirma la reserva
```

Si el pago requerido no se confirma:

```text
NO SE CREA UNA RESERVA CONFIRMADA
```

El sistema puede utilizar mecanismos técnicos temporales para mantener disponible el proceso de pago, pero estos no deben mostrarse como una reserva del cliente ni bloquear indefinidamente el horario.

## 7.3 Reserva manual

El encargado/dueño/cajero autorizado puede crear una reserva manual.

Origen habitual:

* WhatsApp;
* teléfono;
* presencial;
* otros canales administrativos.

Una reserva manual puede existir sin ningún pago.

Ejemplo:

```text
Reserva confirmada
Total: $20.000
Pagado: $0
Restante: $20.000
```

Posteriormente se pueden registrar uno o varios pagos.

---

# 8. Pagos

Una reserva puede tener **cero, uno o muchos pagos**.

Los pagos son entidades independientes de la reserva.

Cada pago debe registrar como mínimo:

* reserva;
* importe;
* medio de pago;
* estado;
* fecha/hora;
* usuario que lo registró cuando corresponda;
* referencia/transacción cuando corresponda.

Medios iniciales:

* efectivo;
* Mercado Pago;
* transferencia;
* posnet.

La lista debe ser extensible y no debe quedar rígidamente limitada a estos medios si posteriormente se incorporan otros.

## 8.1 Múltiples pagos

Una misma reserva puede tener pagos con diferentes medios.

Ejemplo:

```text
Reserva: $20.000

Seña:
Mercado Pago → $8.000

Al finalizar:
Efectivo → $4.000
Mercado Pago → $3.000
Efectivo → $5.000

Total pagado → $20.000
Saldo → $0
```

No es necesario registrar qué jugador aportó cada pago.

El saldo se calcula:

```text
saldo = precio_total - suma(pagos aprobados)
```

## 8.2 Pagos por jugadores

La reserva puede manejar una cantidad de jugadores.

El sistema puede mostrar jugadores genéricos:

```text
Jugador 1
Jugador 2
Jugador 3
...
```

El nombre de cada jugador es **opcional**.

El complejo puede utilizar este mecanismo para controlar quién pagó sin exigir que los jugadores tengan una cuenta.

No se debe obligar a registrar nombres.

## 8.3 Cantidad de jugadores y precio

La forma de calcular el precio según cantidad de jugadores es configurable por negocio/cancha.

Ejemplos:

### Precio fijo

```text
10 jugadores → $20.000
15 jugadores → $20.000
25 jugadores → $20.000
```

### Precio variable

```text
10 jugadores → $20.000
12 jugadores → $24.000
14 jugadores → $28.000
```

No asumir que fútbol 5 implica siempre una cantidad determinada de jugadores.

---

# 9. Mercado Pago

Mercado Pago se utiliza para pagos online y puede utilizarse también para pagos registrados posteriormente desde el panel cuando corresponda.

## Webhook

El webhook debe:

1. recibir la notificación;
2. registrar la notificación;
3. consultar el pago directamente a Mercado Pago;
4. verificar los datos reales del pago;
5. verificar importe;
6. verificar referencia;
7. verificar que corresponda al negocio/reserva;
8. procesar de forma idempotente.

Nunca confiar únicamente en el cuerpo de la notificación.

Un mismo pago no puede generar dos registros de pago aprobados.

`mp_payment_id` debe ser único cuando corresponda.

---

# 10. Cancelaciones y devoluciones

El cliente puede cancelar desde su enlace público cuando la política del negocio lo permita.

La ventana para devolución es configurable.

Ejemplo:

```text
Reserva: 18:00
Ventana de devolución: 2 horas

Cancelación 15:30 → corresponde devolución
Cancelación 16:30 → no corresponde devolución
```

Los valores anteriores son solamente ejemplos.

## 10.1 Si corresponde devolución

El sistema debe mostrar claramente:

```text
Corresponde devolución: $8.000
```

El administrador ejecuta la devolución.

Para pagos de Mercado Pago:

* mostrar el identificador de la transacción;
* recomendar realizar la devolución por el mismo medio;
* el administrador realiza la operación en Mercado Pago durante el MVP;
* luego registra la devolución en CanchaMania.

También debe existir la posibilidad de registrar una devolución en efectivo cuando corresponda.

## 10.2 Reservas manuales

Si una reserva manual no tiene pagos:

```text
Cancelar
→ liberar horario
→ no existe devolución
```

Si tiene pagos, se analiza la política de devolución exactamente igual.

Ejemplo:

```text
WhatsApp
→ reserva creada por encargado
→ seña en efectivo
→ cancelación
→ corresponde devolución
→ devolución en efectivo
```

O:

```text
WhatsApp
→ reserva creada por encargado
→ seña mediante Mercado Pago
→ cancelación
→ corresponde devolución
→ devolución por Mercado Pago recomendada
```

## 10.3 Registro de devolución

Toda devolución debe conservar:

* importe;
* medio;
* fecha;
* usuario que la registró;
* pago relacionado;
* referencia cuando corresponda.

---

# 11. No-show y deuda

El no-show es un estado registrado por el personal.

No debe determinarse automáticamente solamente por el paso del tiempo.

Cuando se marca una reserva como `NO_ASISTIO`:

* se registra quién lo hizo;
* fecha/hora;
* reserva afectada;
* información necesaria para auditoría.

## Política de no-show

Cada negocio puede configurar:

* si genera deuda;
* qué importe genera como deuda;
* si bloquea nuevas reservas mientras exista deuda;
* condiciones adicionales de la política.

Ejemplo:

```text
Reserva: $20.000
Pagado: $0
No asistió

Política del negocio:
Generar deuda → Sí
Bloquear nuevas reservas → Sí

Deuda → $20.000
```

Si el bloqueo está activo:

* el cliente/grupo no puede realizar una nueva reserva online;
* el personal tampoco puede crear una nueva reserva para ese cliente/grupo mientras exista deuda, salvo que la configuración contemple una excepción.

La deuda queda asociada al cliente/grupo correspondiente.

Una vez saldada, el bloqueo desaparece.

---

# 12. Extensión de reservas

Una reserva puede ocupar múltiples horas consecutivas.

El personal autorizado puede extender una reserva desde el panel.

La duración de las extensiones debe ser configurable.

Ejemplo:

```text
22:00 → 23:00
Total: $20.000
Pagado: $8.000
Restante: $12.000

Extensión: +30 minutos
Costo adicional: $10.000

Nuevo total: $30.000
Pagado: $8.000
Nuevo saldo: $22.000
```

No se exige una nueva seña por la extensión.

La extensión debe:

* comprobar disponibilidad;
* recalcular el total;
* mantener los pagos existentes;
* recalcular el saldo;
* registrar quién realizó la extensión;
* registrar fecha/hora;
* registrar el importe adicional.

---

# 13. Grupos fijos

**Grupos fijos es un único concepto de negocio.**

Ejemplo:

```text
Grupo: Aston Birra
Cancha: Cancha 1
Día: viernes
Hora: 19:00
Duración: 1 hora
```

Esto significa que el grupo tiene reservado recurrentemente ese horario.

Si el grupo no juega un viernes determinado:

* se libera solamente esa fecha;
* el grupo mantiene su horario fijo;
* el viernes siguiente vuelve a corresponderle automáticamente.

No convertir una liberación puntual en una modificación permanente del grupo.

## Confirmación de asistencia

El sistema debe permitir configurar:

* si se solicita confirmación;
* con cuánta anticipación;
* qué acciones puede realizar el personal ante la respuesta.

Ejemplo:

```text
Viernes 19:00
Aviso configurable antes del turno

→ Confirmar
→ Liberar esta fecha
→ Gestionar manualmente
```

La falta de respuesta **no debe liberar automáticamente el turno**, salvo que el negocio configure explícitamente esa política.

El grupo fijo permanece activo.

---

# 14. Horarios y disponibilidad

Cada sucursal puede definir sus propios:

* días de atención;
* horarios;
* horarios de apertura/cierre;
* excepciones;
* canchas;
* franjas;
* duración;
* precios.

No asumir que todas las sucursales tienen el mismo horario.

La disponibilidad pública debe mostrar solamente horarios que realmente puedan reservarse.

---

# 15. Buffet y ventas

## Productos

* categoría;
* nombre;
* precio;
* costo opcional;
* controla stock;
* stock actual;
* stock mínimo;
* activo.

El precio histórico de una venta se conserva en `ItemVenta`.

Modificar el precio de un producto no modifica ventas anteriores.

## Stock

Cada movimiento de stock debe quedar registrado.

Tipos iniciales:

* venta;
* compra;
* ajuste;
* anulación.

El stock negativo debe ser configurable.

## Venta rápida

Una venta puede:

* cobrarse inmediatamente;
* quedar asociada a una reserva;
* formar parte de la cuenta del turno.

Una venta asociada a una reserva puede cobrarse junto con el saldo de la cancha.

---

# 16. Caja

La caja pertenece a una sucursal.

MVP:

* una sola caja abierta por sucursal;
* apertura con monto inicial;
* ingresos;
* egresos;
* movimientos manuales;
* cierre;
* arqueo;
* diferencia;
* historial.

Cobros en efectivo y operaciones que requieran caja abierta deben bloquearse si no existe una caja abierta.

## Cálculo

```text
monto_esperado =
monto_inicial
+ ingresos_efectivo
- egresos_efectivo
```

```text
diferencia =
monto_contado - monto_esperado
```

Una caja cerrada no se modifica.

Las correcciones posteriores deben realizarse mediante movimientos de ajuste.

Debe registrarse:

* usuario que abrió;
* usuario que cerró;
* fecha/hora;
* movimientos;
* arqueo.

---

# 17. Auditoría

Registrar usuario y fecha/hora de operaciones relevantes, como:

* cancelación de reserva;
* no-show;
* devolución;
* extensión;
* cambio de precio;
* ajuste de stock;
* anulación de venta;
* apertura/cierre de caja;
* movimientos manuales;
* cambios de configuración;
* cambios relevantes de reservas;
* acciones administrativas sobre pagos.

---

# 18. Modelo de datos inicial

El modelo definitivo se implementará después del diagnóstico técnico de cada etapa.

## Negocio

Representa al cliente de CanchaMania.

Datos posibles:

* nombre;
* estado;
* suscripción;
* configuración general;
* credenciales de Mercado Pago.

## Sucursal / Complejo

* negocio;
* nombre;
* slug;
* teléfono;
* dirección;
* activo;
* zona horaria;
* configuración operativa.

## Membresía

* usuario;
* negocio/sucursal según diseño aprobado;
* rol;
* activa.

## Configuración

Debe contener únicamente reglas que realmente sean configurables.

No convertir valores de ejemplo en constantes de negocio.

## Cancha

* sucursal;
* nombre;
* tipo;
* activa;
* orden.

## Franja / configuración horaria

Debe permitir representar:

* día;
* hora;
* duración;
* precio;
* reglas de disponibilidad.

## Cliente

* sucursal/ámbito correspondiente;
* nombre;
* celular;
* email opcional;
* contador de no-shows;
* notas.

## Reserva

Debe contemplar:

* sucursal;
* cancha;
* cliente;
* fecha;
* hora inicio;
* hora fin;
* precio total;
* estado;
* origen;
* notas;
* creada por;
* token público;
* información de jugadores;
* relación con pagos.

No almacenar `monto_pagado` como fuente de verdad si puede calcularse a partir de los pagos.

## Pago

Un pago puede pertenecer a una reserva o a una venta.

Debe contemplar:

* reserva nullable;
* venta nullable;
* monto;
* método;
* estado;
* identificador de Mercado Pago cuando corresponda;
* referencia;
* usuario;
* fecha;
* información de devolución.

## Grupo fijo

Debe contemplar la recurrencia y las excepciones de fechas sin destruir la configuración recurrente.

## Venta / ItemVenta

Mantener el precio histórico de cada producto vendido.

## Caja / MovimientoCaja

La caja pertenece a una sucursal.

Los movimientos deben distinguir claramente:

* efectivo;
* otros medios;
* ingresos;
* egresos;
* concepto;
* referencia.

---

# 19. API

Prefijo:

```text
/api/
```

## Pública

Ejemplos:

```text
GET  /api/public/negocios/<slug>/
GET  /api/public/sucursales/<slug>/
GET  /api/public/sucursales/<slug>/disponibilidad/
POST /api/public/sucursales/<slug>/reservas/
GET  /api/public/reservas/<token>/
POST /api/public/reservas/<token>/cancelar/
POST /api/webhooks/mercadopago/
```

Los endpoints públicos deben aplicar medidas de protección adecuadas, incluyendo rate limiting cuando corresponda.

## Panel

Recursos iniciales:

```text
/api/reservas/
/api/pagos/
/api/grupos-fijos/
/api/clientes/
/api/canchas/
/api/franjas/
/api/productos/
/api/categorias/
/api/stock/
/api/ventas/
/api/caja/
/api/reportes/
/api/configuracion/
/api/usuarios/
```

Todos los endpoints autenticados deben verificar permisos y aislamiento multi-tenant.

Formato uniforme de errores:

```json
{
  "codigo": "...",
  "mensaje": "..."
}
```

---

# 20. Pantallas

## Pública

* Selección de sucursal.
* Fecha.
* Cancha.
* Horario.
* Datos del cliente.
* Cantidad de jugadores cuando corresponda.
* Resumen.
* Pago.
* Confirmación.
* Consulta de reserva.
* Cancelación.

## Panel

### Reservas

* Grilla.
* Nueva reserva manual.
* Detalle.
* Pagos.
* Saldo.
* Jugadores.
* Consumo.
* Cobros.
* Cancelación.
* No-show.
* Extensión.

### Grupos fijos

* Listado.
* Alta.
* Edición.
* Estado.
* Próximas ocurrencias.
* Confirmación/liberación de fechas individuales.

### Clientes

* Listado.
* Historial.
* No-shows.
* Deudas.
* Reservas.

### Ventas

* Venta rápida.
* Productos.
* Carrito.
* Medio de pago.
* Asociar a reserva.

### Productos y stock

* Categorías.
* Productos.
* Ajustes.
* Compras.
* Alertas.

### Caja

* Apertura.
* Estado actual.
* Movimientos.
* Cobros.
* Egresos.
* Arqueo.
* Cierre.
* Historial.

### Reportes

* Caja.
* Métodos de pago.
* Ocupación.
* Reservas.
* No-shows.
* Deudas.
* Ventas.

### Configuración

* Sucursal.
* Horarios.
* Canchas.
* Franjas.
* Precios.
* Señas.
* Cancelaciones.
* Devoluciones.
* No-show.
* Extensiones.
* Grupos fijos.
* Mercado Pago.
* Otras reglas parametrizables.

### Usuarios

* Alta.
* Baja/desactivación.
* Roles.
* Membresías.

---

# 21. Estructura del proyecto

## Frontend

```text
frontend/src/

├── main.js
├── App.vue
├── router/
├── api/
│   ├── client.js
│   └── ...Api.js
├── layouts/
├── components/ui/
├── composables/
└── modules/
    ├── auth/
    ├── publico/
    ├── reservas/
    ├── pagos/
    ├── gruposFijos/
    ├── clientes/
    ├── ventas/
    ├── productos/
    ├── stock/
    ├── caja/
    ├── reportes/
    ├── configuracion/
    └── usuarios/
```

Reglas:

* Un componente por archivo.
* Componentes agrupados por módulo.
* No concentrar lógica en `index`.
* Los componentes no llaman directamente a la API.
* Usar API modules y/o stores.
* Componentes grandes deben dividirse.
* Montos mediante un único composable.
* Rutas con metadatos de permisos.
* Backend como fuente real de autorización.

## Backend

```text
backend/

├── config/
└── apps/
    ├── negocios/
    ├── sucursales/
    ├── reservas/
    ├── pagos/
    ├── buffet/
    └── caja/
```

Cada aplicación debe separar cuando corresponda:

```text
models.py
services.py
serializers.py
views.py
permissions.py
urls.py
management/
tests/
```

La lógica de negocio debe vivir en `services.py`, no en las vistas ni serializers.

---

# 22. Reglas técnicas obligatorias

## Dinero

Usar `Decimal`.

Nunca utilizar `float` para dinero.

## Concurrencia

La creación/modificación de reservas debe ser segura ante operaciones simultáneas.

No confiar únicamente en validaciones del frontend.

Debe existir protección de base de datos y transacciones apropiadas.

## Multi-tenancy

Toda consulta autenticada debe respetar el ámbito del usuario.

Debe haber tests de aislamiento.

## Pagos

Los webhooks deben ser idempotentes.

Nunca confiar solamente en una notificación externa sin verificar el pago.

## Seguridad

* CSRF.
* Protección de endpoints públicos.
* Rate limiting donde corresponda.
* Secretos fuera del repositorio.
* Credenciales sensibles cifradas.
* Validación de permisos en backend.

---

# 23. Orden de construcción

Cada etapa se termina, prueba y revisa antes de comenzar la siguiente.

| # | Etapa                    | Terminado cuando                                                                  |
| - | ------------------------ | --------------------------------------------------------------------------------- |
| 1 | Base                     | Django + Vue + PostgreSQL + usuarios + negocio/sucursales + membresías + permisos |
| 2 | Canchas y horarios       | Configuración de canchas, horarios y disponibilidad                               |
| 3 | Reservas                 | Reservas manuales, reservas online y prevención de doble reserva                  |
| 4 | Clientes y grupos fijos  | Clientes, no-show, deudas configurables y grupos fijos                            |
| 5 | Pagos + Mercado Pago     | Pagos múltiples, webhook, seña, cancelaciones y devoluciones                      |
| 6 | Buffet y stock           | Productos, ventas y stock                                                         |
| 7 | Caja                     | Apertura, cobros, movimientos, arqueo y cierre                                    |
| 8 | Reportes y configuración | Reportes y parametrización completa                                               |
| 9 | WhatsApp/pulido/piloto   | Pruebas con complejos reales y deploy                                             |

No adelantar funcionalidad de etapas posteriores.

---

# 24. Reglas para OpenCode

1. Leer este documento completo antes de modificar código.
2. Trabajar únicamente en la etapa solicitada.
3. No adelantar funcionalidades.
4. No agregar funcionalidades de la sección "NO entra".
5. No modificar una regla de negocio definida aquí sin consultar primero.
6. Si una implementación contradice el SPEC, detenerse y señalar la contradicción.
7. No asumir reglas comerciales.
8. Todo valor comercial configurable debe evitar hardcodearse.
9. Diagnosticar primero y modificar después.
10. Antes de cambios importantes, explicar qué archivos se modificarán y por qué.
11. Mantener la separación por módulos.
12. La lógica de negocio debe estar en servicios.
13. Toda consulta del panel debe respetar el aislamiento multi-tenant.
14. Toda funcionalidad crítica debe tener tests.
15. Probar especialmente:

    * doble reserva;
    * concurrencia;
    * aislamiento entre negocios/sucursales;
    * pagos duplicados;
    * webhook repetido;
    * cancelaciones;
    * devoluciones;
    * no-show;
    * deudas;
    * extensiones;
    * caja;
    * stock.
16. Usar credenciales de Mercado Pago de prueba durante desarrollo.
17. Nunca guardar secretos en código.
18. No utilizar `float` para dinero.
19. Al terminar una tarea informar:

    * archivos creados;
    * archivos modificados;
    * cambios realizados;
    * tests ejecutados;
    * resultado de los tests;
    * pendientes;
    * posibles riesgos encontrados.
20. No refactorizar código no relacionado con la tarea sin autorización.

---

# 25. Decisiones ya definidas

Las siguientes decisiones forman parte del diseño aprobado:

* Un negocio puede tener múltiples sucursales.
* Una cuenta de Mercado Pago puede utilizarse para las sucursales de un mismo negocio.
* CanchaMania no intermedia los fondos.
* Las reservas online requieren pago para confirmarse.
* No existe `pendiente_pago` como estado de reserva.
* Una reserva puede tener múltiples pagos.
* Los pagos pueden utilizar distintos medios.
* Los pagos no necesitan identificar al jugador que aportó el dinero.
* Puede existir una lista de jugadores genéricos.
* El nombre del jugador es opcional.
* El precio según cantidad de jugadores es configurable.
* Las reservas manuales pueden existir sin pagos.
* El no-show es registrado por el personal.
* La deuda por no-show es configurable.
* El bloqueo por deuda es configurable.
* Las cancelaciones pueden generar devolución según política configurable.
* Las devoluciones se ejecutan inicialmente de forma manual.
* Mercado Pago es el medio recomendado cuando el pago original fue realizado por Mercado Pago.
* También se puede registrar devolución en efectivo.
* Las extensiones de reserva son posibles desde el panel.
* La duración de extensiones es configurable.
* Los grupos fijos mantienen su recurrencia aunque se libere una fecha puntual.
* Los horarios son configurables por sucursal.
* La caja pertenece a una sucursal.
* No se deben hardcodear reglas comerciales.

---

# 26. Decisiones pendientes

Estas decisiones todavía deben definirse antes de implementar la funcionalidad correspondiente.

* Duración y reglas exactas de las franjas horarias.
* Estructura definitiva del cálculo de precios por cantidad de jugadores.
* Detalle de las políticas de devolución.
* Reglas exactas de pago de deudas.
* Métodos de pago adicionales.
* Reglas detalladas de grupos fijos.
* Reglas detalladas de horarios excepcionales/feriados.
* Reportes definitivos.
* Diseño definitivo de WhatsApp.
* Suscripción comercial de CanchaMania.
* Nombre/dominio definitivo si se decide modificar CanchaMania.

**No implementar una decisión pendiente mediante una suposición.**
