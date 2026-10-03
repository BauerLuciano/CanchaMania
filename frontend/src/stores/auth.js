/**
 * Store de sesion (Pinia).
 *
 * Guarda exactamente lo que devuelve `GET /api/auth/me/` y nada mas.
 *
 * Regla central del proyecto: **el backend es la autoridad del permiso**. El
 * frontend usa `perfil.permisos` para decidir que mostrar, pero no puede
 * otorgarse permisos que el backend no devolvio. `tiene()` solo consulta ese
 * conjunto: no hay atajos, ni un caso especial para superadmin, ni un valor por
 * defecto que conceda acceso. La autorizacion real ocurre en cada endpoint, y
 * un endpoint que no exige permiso igual respondera 403 aunque la pantalla se
 * haya mostrado.
 */
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import * as authApi from '../api/authApi.js'
import { obtenerTokenCsrf } from '../api/client.js'

export const useAuthStore = defineStore('auth', () => {
  /** Perfil devuelto por el backend, o `null` si no hay sesion. */
  const perfil = ref(null)
  /** Hay una operacion de sesion en curso (login o logout). */
  const ocupado = ref(false)
  /** Ya se intento recuperar la sesion al arrancar la app. */
  const inicializado = ref(false)
  /** Ultimo error de sesion, para mostrarlo sin romper la navegacion. */
  const error = ref(null)

  // Promesa compartida: varias llamadas concurrentes a `restaurar()` (la guarda
  // de rutas y el montaje) hacen una sola peticion a `/api/auth/me/`.
  let promesaRestaurar = null

  const autenticado = computed(() => perfil.value !== null)
  const esSuperadmin = computed(() => Boolean(perfil.value?.es_superadmin))

  /**
   * Permisos efectivos, tal cual los devolvio el backend.
   *
   * Sin transformarlos ni completarlos: si el backend no lo listo, no existe.
   */
  const permisos = computed(() => new Set(perfil.value?.permisos ?? []))

  const roles = computed(() => [...(perfil.value?.roles ?? [])])
  const negocios = computed(() => perfil.value?.negocios ?? [])
  const sucursales = computed(() => perfil.value?.sucursales ?? [])
  const ambitos = computed(() => perfil.value?.ambitos ?? [])

  const nombreMostrado = computed(() => perfil.value?.nombre || perfil.value?.email || '')
  const iniciales = computed(() => {
    const partes = nombreMostrado.value.trim().split(/\s+/).filter(Boolean)
    return partes
      .slice(0, 2)
      .map((p) => p[0]?.toUpperCase() ?? '')
      .join('')
  })

  /**
   * Indica si el backend devolvio el permiso indicado.
   *
   * Es una consulta de pertenencia al conjunto recibido. No hay ningun camino
   * por el que esta funcion conceda algo que `perfil.permisos` no tenga.
   */
  function tiene(permiso) {
    if (typeof permiso !== 'string' || permiso === '') return false
    return permisos.value.has(permiso)
  }

  /** `true` si el backend devolvio al menos uno de los permisos indicados. */
  function tieneAlguno(lista) {
    return Array.isArray(lista) && lista.some((p) => tiene(p))
  }

  /** `true` si el usuario tiene alcance sobre todo el negocio en alguno. */
  function tieneAlcanceTotal() {
    return negocios.value.some((negocio) => negocio.todo_el_negocio)
  }

  /**
   * Recupera la sesion al arrancar.
   *
   * Un 401 es el caso normal de una pagina abierta sin sesion, no un fallo: se
   * deja `perfil` en `null` y se sigue. Cualquier otro error tambien se
   * absorbe para que la guarda de rutas nunca quede esperando; queda
   * registrado en `error` para poder avisar.
   */
  async function restaurar() {
    if (promesaRestaurar) return promesaRestaurar
    if (inicializado.value) return

    promesaRestaurar = (async () => {
      try {
        perfil.value = await authApi.perfilActual()
        error.value = null
      } catch (excepcion) {
        perfil.value = null
        error.value = excepcion.sesionCaida ? null : excepcion
      } finally {
        inicializado.value = true
      }
    })()

    try {
      return await promesaRestaurar
    } finally {
      promesaRestaurar = null
    }
  }

  /**
   * Inicia sesion.
   *
   * El backend devuelve el perfil ya completo dentro de `usuario`, asi que no
   * hace falta un `me` extra. Cualquier error se propaga para que la pantalla
   * de login muestre el mensaje del backend (`CREDENCIALES_INVALIDAS`,
   * `SIN_AMBITO`, `CSRF_INVALIDO`...).
   */
  async function ingresar({ email, contrasena }) {
    ocupado.value = true
    error.value = null
    try {
      const respuesta = await authApi.entrar({ email, contrasena })
      perfil.value = respuesta?.usuario ?? null
      inicializado.value = true
      return perfil.value
    } catch (excepcion) {
      error.value = excepcion
      perfil.value = null
      throw excepcion
    } finally {
      ocupado.value = false
    }
  }

  /**
   * Cierra la sesion.
   *
   * El estado local se limpia siempre, incluso si la peticion falla: si el
   * backend ya no tiene sesion, quedarse mostrando el panel seria mentir.
   */
  async function cerrar() {
    ocupado.value = true
    try {
      await authApi.salir()
    } catch (excepcion) {
      error.value = excepcion
    } finally {
      await olvidarLocal()
      ocupado.value = false
    }
  }

  /**
   * Descarta la sesion sin pegarle al backend.
   *
   * Se usa cuando la API responde 401 en cualquier punto: el backend ya decidio
   * que la sesion no existe.
   */
  async function olvidarLocal() {
    perfil.value = null
    inicializado.value = true
    // `login()` y `logout()` rotan el secreto CSRF del servidor. El cliente
    // ya lee la cookie nueva en cada escritura, pero se fuerza el refresco para
    // no dejar el proximo ingreso dependiendo de que la cookie haya llegado.
    try {
      await obtenerTokenCsrf({ forzar: true })
    } catch {
      // Si no se puede renovar, la proxima escritura lo pide de nuevo. No es
      // motivo para dejar el logout a medias.
    }
  }

  /** Limpia el error de sesion (por ejemplo, al reintentar un login). */
  function limpiarError() {
    error.value = null
  }

  return {
    perfil,
    ocupado,
    inicializado,
    error,
    autenticado,
    esSuperadmin,
    permisos,
    roles,
    negocios,
    sucursales,
    ambitos,
    nombreMostrado,
    iniciales,
    tiene,
    tieneAlguno,
    tieneAlcanceTotal,
    restaurar,
    ingresar,
    cerrar,
    olvidarLocal,
    limpiarError,
  }
})
