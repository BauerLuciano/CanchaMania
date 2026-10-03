/**
 * Decision de la guarda de rutas, como funcion pura.
 *
 * Vive separada de `router/index.js` para poder probarla sin montar un router:
 * recibe el estado que necesita y devuelve `true` (deja pasar) o un objeto de
 * redireccion.
 *
 * El permiso de cada ruta viaja en `meta.permiso` (SPEC §21: "Rutas con
 * metadatos de permisos") y se contrasta contra lo que el backend devolvio. Si
 * el backend no devolvio el permiso, la ruta no se abre: pero el aviso es
 * "sin permisos", no "no encontrado", porque acá sabemos que la ruta existe.
 * Que el dato real este disponible o no lo decide el endpoint, no esta guarda.
 */

/** Destino al que va quien entra sin sesion. */
export const RUTA_LOGIN = 'login'

/** Destino al que va un usuario autenticado que solo quiere ver el panel. */
export const RUTA_PANEL = 'panel'

/** Pantalla de aviso cuando falta el permiso de una ruta. */
export const RUTA_SIN_PERMISOS = 'sin-permiso'

/**
 * @param {object} entrada
 * @param {object} entrada.to            Ruta de destino (Vue Router).
 * @param {boolean} entrada.autenticado  Si hay sesion.
 * @param {(permiso: string) => boolean} entrada.tiene Consulta de permisos.
 * @returns {true|{name: string, query?: object, replace?: boolean}}
 */
export function decidirNavegacion({ to, autenticado, tiene }) {
  // Una ruta que declara permiso es una ruta que exige sesion, se haya
  // declarado o no `requiereAuth`: no tiene sentido consultar el perfil de
  // permisos de alguien que todavia no entro. Dejarlo implicito evita el
  // error de escribir una ruta con permiso y sin `requiereAuth`, que abriria
  // la pantalla a cualquiera y recien despues la cerraria.
  const exigeSesion =
    to.matched.some((registro) => registro.meta?.requiereAuth === true) ||
    Boolean(to.meta?.permiso)

  if (exigeSesion && !autenticado) {
    // Se recuerda el destino para volver a el despues de entrar.
    // `replace` evita que el login quede en el historial: si alguien comparte
    // la URL del panel, el boton "atras" no deberia devolverlo al login.
    return {
      name: RUTA_LOGIN,
      query: to.fullPath && to.fullPath !== '/' ? { next: to.fullPath } : {},
      replace: true,
    }
  }

  // Ya autenticado: el login no tiene nada que ofrecer.
  if (!exigeSesion && to.name === RUTA_LOGIN && autenticado) {
    return { name: RUTA_PANEL, replace: true }
  }

  // Ruta protegida por permiso: se consulta lo que el backend devolvio.
  const permiso = to.meta?.permiso
  if (permiso && !tiene(permiso)) {
    return {
      name: RUTA_SIN_PERMISOS,
      query: { de: to.fullPath },
      replace: true,
    }
  }

  return true
}

/**
 * Arma el middleware de navegacion.
 *
 * Antes de decidir, garantiza que se intento recuperar la sesion: sin eso, un
 * refresco en `/panel` redirigiria al login aunque la cookie siga viva.
 */
export function crearGuardaSesion({ useAuth }) {
  return async function guarda(to) {
    const auth = useAuth()
    if (!auth.inicializado) await auth.restaurar()
    return decidirNavegacion({
      to,
      autenticado: auth.autenticado,
      tiene: (permiso) => auth.tiene(permiso),
    })
  }
}
