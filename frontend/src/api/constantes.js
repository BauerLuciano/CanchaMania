/**
 * Constantes de la capa HTTP.
 *
 * Se separan del cliente para que las pruebas y los modulos de API puedan
 * importar los nombres exactos que espera el backend sin duplicarlos.
 */

/**
 * Prefijo de la API.
 *
 * Relativo a propósito: el frontend y la API comparten origen (SPEC §3), asi
 * que nunca hay un host distinto que configurar ni hace falta CORS. En
 * desarrollo el proxy de Vite reenvia `/api` a Django; en produccion Django
 * sirve el build con WhiteNoise.
 */
export const BASE_API = import.meta.env.VITE_API_BASE_URL || '/api'

/** Verbos que no modifican estado: no necesitan token CSRF. */
export const METODOS_SEGUROS = new Set(['GET', 'HEAD', 'OPTIONS'])

/** Nombre de la cookie que Django escribe con `ensure_csrf_cookie`. */
export const COOKIE_CSRF = 'csrftoken'

/** Cabecera que Django lee para validar el token (Django 4.1+). */
export const NOMBRE_CSRF = 'X-CSRFToken'
