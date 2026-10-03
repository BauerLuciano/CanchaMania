/**
 * Endpoints de sesion (SPEC §19). Unico lugar donde viven estas rutas.
 *
 * Contratos reales del backend:
 *
 * | Ruta                     | Metodo | CSRF | Respuesta                        |
 * |--------------------------|--------|------|----------------------------------|
 * | /api/auth/csrf/          | GET    | -    | { codigo, csrf_token }            |
 * | /api/auth/login/         | POST   | si   | { codigo, usuario: <perfil> }     |
 * | /api/auth/logout/        | POST   | si   | { codigo, mensaje }               |
 * | /api/auth/me/            | GET    | -    | <perfil>                          |
 * | /api/auth/roles/         | GET    | -    | { results: [...] }                |
 *
 * `<perfil>` lo arma `GET /api/auth/me/`: identidad, roles, ambitos y la lista
 * de permisos efectivos. Los permisos los calcula el backend.
 */
import { api, obtenerTokenCsrf } from './client.js'

export const RUTAS_AUTH = {
  csrf: '/auth/csrf/',
  login: '/auth/login/',
  logout: '/auth/logout/',
  me: '/auth/me/',
  roles: '/auth/roles/',
}

/** Pide (o renueva) el token CSRF antes de escribir. */
export function pedirTokenCsrf(forzar = false) {
  return obtenerTokenCsrf({ forzar })
}

/**
 * Inicia sesion por email y contrasena.
 *
 * El backend exige CSRF tambien aca, y ademas rechaza con `SIN_AMBITO` a quien
 * no tenga ninguna membresia activa: en ese caso ni siquiera se abre sesion.
 */
export function entrar({ email, contrasena }) {
  return api.post(RUTAS_AUTH.login, { email, contrasena })
}

/** Cierra la sesion. CSRF obligatorio. */
export function salir() {
  return api.post(RUTAS_AUTH.logout)
}

/** Perfil del usuario autenticado, con sus permisos efectivos. */
export function perfilActual() {
  return api.get(RUTAS_AUTH.me)
}

/** Catalogo tecnico de roles, para no inventar roles en el frontend. */
export function catalogoRoles() {
  return api.get(RUTAS_AUTH.roles)
}
