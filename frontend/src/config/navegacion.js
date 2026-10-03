/**
 * Navegacion del panel, declarada en un solo lugar.
 *
 * Cada seccion dice que permiso del backend necesita para aparecer. La pantalla
 * filtra con `auth.tiene(seccion.permiso)`: si el backend no devolvio ese
 * permiso, la seccion no se muestra. No hay logica de roles duplicada aqui: los
 * codigos son exactamente los que devuelve `/api/auth/me/`, y el backend es el
 * que decide quien los tiene.
 *
 * Los permisos NO significan que la operacion este autorizada: significan que la
 * seccion se dibuja. Cada endpoint vuelve a validar por su cuenta, y si el
 * alcance real es mas acotado que el permiso, la API responde 403 o 404.
 */

export const SECCIONES = [
  {
    id: 'panel',
    titulo: 'Panel',
    descripcion: 'Resumen del esqueleto del sistema.',
    ruta: { name: 'panel' },
    permiso: null,
    disponible: true,
  },
  {
    id: 'acceso',
    titulo: 'Mi acceso',
    descripcion: 'Roles, ambitos y permisos que devolvio el backend.',
    ruta: { name: 'acceso' },
    permiso: null,
    disponible: true,
  },
]

/**
 * Secciones de las etapas siguientes.
 *
 * Ya declaran el permiso que las habilita, pero `disponible: false` porque la
 * pantalla todavia no existe. Se dibujan bloqueadas y sin enlace: es preferible
 * mostrar que falta a inventar una ruta que lleve a una pantalla vacia.
 *
 * Los codigos salen de `PERMISOS_POR_ROL` del backend; si el backend los cambia,
 * estas entradas dejan de coincidir y las secciones no aparecen, que es el
 * fallo seguro.
 */
export const SECCIONES_PENDIENTES = [
  {
    id: 'negocios',
    titulo: 'Negocios',
    descripcion: 'Alta y datos del negocio. El alta sigue siendo por comando.',
    permiso: 'negocios.view_negocio',
  },
  {
    id: 'sucursales',
    titulo: 'Sucursales',
    descripcion: 'Sedes, zona horaria y estado.',
    permiso: 'sucursales.view_sucursal',
  },
  {
    id: 'usuarios',
    titulo: 'Usuarios',
    descripcion: 'Personas con acceso al ambito.',
    permiso: 'cuentas.view_usuario',
  },
  {
    id: 'membresias',
    titulo: 'Membresias',
    descripcion: 'Que usuario accede a que negocio o sede, con que rol.',
    permiso: 'cuentas.view_membresia',
  },
]
