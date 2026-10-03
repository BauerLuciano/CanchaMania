/**
 * Cliente HTTP unico de CanchaMania (SPEC §21: "Cliente HTTP unico en
 * src/api/client.js").
 *
 * Concentra lo que TODA peticion necesita:
 *
 * 1. La cookie de sesion (`credentials: 'include'`). No hay JWT (SPEC §3).
 * 2. El token CSRF en `X-CSRFToken` para los metodos que escriben. El backend
 *    lo exige tambien en el login: sin el, un sitio externo podria iniciar
 *    sesion en el navegador de la persona con su cuenta.
 * 3. La traduccion de las respuestas de error a un unico tipo, `ApiError`, con
 *    el `codigo` estable del backend (SPEC §19). Ningun modulo tiene que
 *    interpretar el cuerpo crudo ni adivinar por el status.
 *
 * Ningun componente ni vista debe usar `fetch` directamente.
 */
import { BASE_API, COOKIE_CSRF, METODOS_SEGUROS, NOMBRE_CSRF } from './constantes.js'

/** Codigo local para fallos de red: no viene del backend, asi que se define aqui. */
export const ERROR_DE_RED = 'ERROR_DE_RED'

/**
 * Error de la API, ya normalizado.
 *
 * `codigo` y `mensaje` salen del backend; `estado` es el status HTTP y
 * `detalles` son los errores por campo cuando la validacion falla.
 */
export class ApiError extends Error {
  constructor({ codigo, mensaje, detalles = null, estado = 0 }) {
    super(mensaje)
    this.name = 'ApiError'
    this.codigo = codigo ?? 'ERROR_DESCONOCIDO'
    this.mensaje = mensaje ?? 'Ocurrio un error inesperado.'
    this.detalles = detalles
    this.estado = estado
  }

  /** La sesion no existe o caduco: hay que volver a entrar. */
  get sesionCaida() {
    return this.estado === 401
  }

  /** CSRF ausente o desfasado: se puede reintentar con un token nuevo. */
  get csrfInvalido() {
    return this.codigo === 'CSRF_INVALIDO'
  }

  /** El backend respondio 403 por permisos o por ambito. */
  get sinPermisos() {
    return this.estado === 403
  }

  /** Validacion de campos: el detalle viene en `detalles`. */
  get validacion() {
    return this.codigo === 'VALIDACION_INVALIDA'
  }

  /** Mensaje de un campo concreto, o `null` si el campo no tiene error. */
  errorDe(campo) {
    const valor = this.detalles?.[campo]
    if (valor === undefined || valor === null) return null
    return Array.isArray(valor) ? valor.join(' ') : String(valor)
  }
}

// --- Token CSRF --------------------------------------------------------------

let tokenCsrf = null
let promesaCsrf = null

/** Lee el token de la cookie `csrftoken`. */
export function leerCookieCsrf() {
  if (typeof document === 'undefined') return null
  const prefijo = `${COOKIE_CSRF}=`
  const trozo = document.cookie.split('; ').find((p) => p.startsWith(prefijo))
  return trozo ? decodeURIComponent(trozo.slice(prefijo.length)) : null
}

/**
 * Resuelve una ruta de la API contra el origen actual.
 *
 * Toda peticion sale con URL absoluta para que `ejecutar` no tenga que suponer
 * si lo que recibe es relativa o completa. La base es el origen del documento,
 * nunca un host configurable: el frontend y la API comparten dominio (SPEC §3).
 */
function urlAbsoluta(ruta, params) {
  const limpia = ruta.startsWith('/') ? ruta : `/${ruta}`
  const url = new URL(`${BASE_API}${limpia}`, window.location.origin)
  for (const [clave, valor] of Object.entries(params ?? {})) {
    if (valor !== undefined && valor !== null && valor !== '') {
      url.searchParams.set(clave, String(valor))
    }
  }
  return url.toString()
}

/**
 * Devuelve (y memoriza) el token CSRF, pidiendolo al backend si hace falta.
 *
 * Se pide a `GET /api/auth/csrf/`, que ademas deja la cookie via
 * `ensure_csrf_cookie`. Las llamadas concurrentes comparten una sola peticion,
 * para que dos formularios que se guarden al mismo tiempo no se pisen.
 *
 * La cookie manda sobre el valor memorizado, y no es un detalle: Django rota
 * el secreto CSRF en cada `login()` para defenderse de la fijacion de sesion y
 * deja la cookie nueva en la respuesta. Si se reusara el token pedido *antes*
 * de entrar, la primera escritura posterior al ingreso fallaria con
 * `CSRF_INVALIDO`. El valor memorizado queda como respaldo para cuando la
 * cookie no se puede leer.
 */
export async function obtenerTokenCsrf({ forzar = false } = {}) {
  const deCookie = leerCookieCsrf()
  if (!forzar && deCookie) {
    tokenCsrf = deCookie
    return tokenCsrf
  }

  if (!forzar && tokenCsrf) return tokenCsrf
  if (!forzar && promesaCsrf) return promesaCsrf

  promesaCsrf = (async () => {
    const respuesta = await ejecutar(urlAbsoluta('/auth/csrf/'), {
      metodo: 'GET',
      cabeceras: { Accept: 'application/json' },
    })

    // El backend devuelve el token enmascarado en el cuerpo; la cookie es el
    // respaldo para cuando el cuerpo no lo trae.
    tokenCsrf = respuesta?.csrf_token ?? leerCookieCsrf()
    return tokenCsrf
  })()

  try {
    return await promesaCsrf
  } finally {
    promesaCsrf = null
  }
}

/**
 * Olvida el token memorizado y descarta la cookie del navegador.
 *
 * Se llama tras un `CSRF_INVALIDO` y tras el logout.
 *
 * Descartar tambien la cookie es lo que permite recuperarse de verdad: si el
 * servidoregyrotate el secreto (o la cookie llego manipulada), pedir un token
 * nuevo sobre la misma cookie mala devolveria siempre la misma cookie mala.
 * Sin cookie, Django emite un secreto nuevo.
 */
export function olvidarTokenCsrf() {
  tokenCsrf = null
  borrarCookieCsrf()
}

function borrarCookieCsrf() {
  if (typeof document === 'undefined') return
  // Solo se borra la cookie propia de la app, sobre el path en que se escribio.
  document.cookie = `${COOKIE_CSRF}=; path=/; max-age=0; samesite=lax`
}

// --- Aviso de sesion caida ----------------------------------------------------

const oyentesSesionCaida = new Set()

/**
 * Registra un escuchador para cuando la API responde 401.
 *
 * Vive aqui y no en el store para que el cliente no dependa de Pinia ni del
 * router (y para que el store no dependa del cliente). `composables/useMontaje.js`
 * es quien lo conecta.
 */
export function alCaerLaSesion(oyente) {
  oyentesSesionCaida.add(oyente)
  return () => oyentesSesionCaida.delete(oyente)
}

function avisarSesionCaida() {
  for (const oyente of [...oyentesSesionCaida]) {
    try {
      oyente()
    } catch (error) {
      console.error('Fallo un escuchador de sesion caida', error)
    }
  }
}

// --- Peticion ----------------------------------------------------------------

/** Ejecuta el `fetch` y normaliza la respuesta. */
async function ejecutar(url, opciones) {
  const metodo = (opciones.metodo ?? 'GET').toUpperCase()
  const cabeceras = { Accept: 'application/json', ...opciones.cabeceras }

  if (!METODOS_SEGUROS.has(metodo)) {
    // Sin token, el backend responde 403 CSRF_INVALIDO. Se pide antes de salir.
    cabeceras[NOMBRE_CSRF] = await obtenerTokenCsrf()
    if (opciones.cuerpo !== undefined && cabeceras['Content-Type'] === undefined) {
      cabeceras['Content-Type'] = 'application/json'
    }
  }

  let respuesta
  try {
    respuesta = await fetch(url, {
      method: metodo,
      credentials: 'include',
      headers: cabeceras,
      body: opciones.cuerpo === undefined ? undefined : JSON.stringify(opciones.cuerpo),
    })
  } catch (error) {
    throw new ApiError({
      codigo: ERROR_DE_RED,
      mensaje: 'No se pudo conectar con el servidor. Revise su conexion e intente de nuevo.',
      estado: 0,
    })
  }

  const datos = await leerCuerpo(respuesta)

  if (!respuesta.ok) {
    const apiError = new ApiError({
      codigo: datos?.codigo,
      mensaje: datos?.mensaje,
      detalles: datos?.detalles ?? null,
      estado: respuesta.status,
    })

    // Un token desfasado no se reintenta solo: se descarta la cookie y el
    // valor memorizado para que la proxima escritura pida uno nuevo al servidor.
    if (apiError.csrfInvalido) olvidarTokenCsrf()
    if (apiError.sesionCaida) avisarSesionCaida()

    throw apiError
  }

  return datos
}

/**
 * Lee el cuerpo de la respuesta.
 *
 * Un 204 o un cuerpo vacio es `null`. Si el backend devolviera HTML (por
 * ejemplo, una pagina de error de Django antes de llegar a la API), se devuelve
 * un error coherente en vez de propagar algo que no es JSON.
 */
async function leerCuerpo(respuesta) {
  if (respuesta.status === 204) return null

  const texto = await respuesta.text().catch(() => '')
  if (!texto) return null

  try {
    return JSON.parse(texto)
  } catch {
    return {
      codigo: 'ERROR_INTERNO',
      mensaje: `Respuesta inesperada del servidor (${respuesta.status}).`,
    }
  }
}

/**
 * Peticion tipada de la API.
 *
 * @param {string} ruta    Ruta relativa al prefijo `/api`, con o sin slash
 *                         inicial: `'auth/me/'` o `'/auth/me/'`.
 * @param {object} opciones
 * @param {string}  opciones.metodo   Verbo HTTP. Por defecto `GET`.
 * @param {object}  opciones.cuerpo   Objeto a serializar como JSON.
 * @param {object}  opciones.params   Query string.
 * @param {object}  opciones.cabeceras Cabeceras adicionales.
 * @returns {Promise<object|null>} Cuerpo ya parseado.
 * @throws {ApiError} Siempre que la respuesta no sea 2xx.
 */
export async function pedir(ruta, { metodo = 'GET', cuerpo, params, cabeceras } = {}) {
  return ejecutar(urlAbsoluta(ruta, params), { metodo, cuerpo, cabeceras })
}

/** Atajos por verbo. Ningun modulo necesita conocer `pedir`. */
export const api = {
  get: (ruta, opciones) => pedir(ruta, { ...opciones, metodo: 'GET' }),
  post: (ruta, cuerpo, opciones) => pedir(ruta, { ...opciones, metodo: 'POST', cuerpo }),
  patch: (ruta, cuerpo, opciones) => pedir(ruta, { ...opciones, metodo: 'PATCH', cuerpo }),
  put: (ruta, cuerpo, opciones) => pedir(ruta, { ...opciones, metodo: 'PUT', cuerpo }),
  delete: (ruta, opciones) => pedir(ruta, { ...opciones, metodo: 'DELETE' }),
}
