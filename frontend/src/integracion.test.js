/**
 * Prueba de integracion de la sesion.
 *
 * Monta la aplicacion real (`App.vue`, router, store y `useMontaje`) contra un
 * backend falso que replica el contrato del Django, incluida la rotacion del
 * token CSRF en el login y el rechazo de `SIN_AMBITO`.
 *
 * `guard.test.js` prueba la decision de la guarda de forma aislada; este prueba
 * el cableado completo: formulario, redireccion, navegacion por permisos y
 * logout.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'

import App from './App.vue'
import rutas from './router/rutas.js'
import { crearGuardaSesion } from './router/guard.js'
import { olvidarTokenCsrf } from './api/client.js'
import { useAuthStore } from './stores/auth.js'

/** Perfil tal como lo arma `GET /api/auth/me/`. */
function perfil({ email, roles, permisos }) {
  return {
    id: 1,
    email,
    nombre: 'Persona Prueba',
    es_superadmin: false,
    roles,
    ambitos: [{ negocio_id: 1, sucursal_id: null, rol: roles[0], ambito: 'negocio' }],
    negocios: [{ id: 1, todo_el_negocio: true, roles, sucursales: [] }],
    sucursales: [],
    permisos,
  }
}

const PERMISOS_DUENO = [
  'cuentas.add_membresia',
  'cuentas.add_usuario',
  'cuentas.change_membresia',
  'cuentas.change_usuario',
  'cuentas.delete_membresia',
  'cuentas.view_membresia',
  'cuentas.view_usuario',
  'negocios.view_negocio',
  'sucursales.add_sucursal',
  'sucursales.change_sucursal',
  'sucursales.delete_sucursal',
  'sucursales.view_sucursal',
]

// Subconjunto real del Cajero: no ve membresias ni puede escribir sucursales.
const PERMISOS_CAJERO = ['cuentas.view_usuario', 'negocios.view_negocio', 'sucursales.view_sucursal']

const CONTRASENA = 'Clave-De-Prueba-123'

const perfilDueno = () => perfil({ email: 'dueno@prueba.test', roles: ['DUENO'], permisos: PERMISOS_DUENO })
const perfilCajero = () =>
  perfil({ email: 'cajero@prueba.test', roles: ['CAJERO'], permisos: PERMISOS_CAJERO })

/**
 * Backend falso.
 *
 * Replica lo que al frontend le importa del backend:
 * - el CSRF es obligatorio y el token se rota en cada `login`;
 * - `me` responde 401 sin sesion;
 * - el login valida credenciales y rechaza con `SIN_AMBITO` a quien no tiene
 *   membresias, sin abrir sesion.
 *
 * @param {object} opciones
 * @param {object|null} opciones.perfil        Perfil que devuelve `me` y `login`.
 * @param {string}      opciones.emailValido   Email aceptado. Por defecto, el
 *                                            del perfil; se separa para poder
 *                                            simular un usuario sin membresias,
 *                                            que igual tiene credenciales
 *                                            correctas.
 * @param {boolean}      opciones.sesionActiva Si la sesion ya esta abierta al
 *                                            cargar la pagina (refresco).
 */
function crearBackend({
  perfil: perfilDevuelto = null,
  emailValido = perfilDevuelto?.email ?? null,
  sesionActiva = false,
} = {}) {
  let sesion = sesionActiva ? perfilDevuelto : null
  const peticiones = []

  const responder = (cuerpo, estado = 200) => ({
    ok: estado < 400,
    status: estado,
    text: async () => JSON.stringify(cuerpo),
  })

  const tokenDe = (opciones) => opciones.headers?.['X-CSRFToken']

  const fake = vi.fn(async (url, opciones = {}) => {
    const ruta = new URL(url, 'http://localhost:3000').pathname
    const metodo = (opciones.method ?? 'GET').toUpperCase()
    peticiones.push({ ruta, metodo, token: tokenDe(opciones) })

    if (ruta === '/api/auth/csrf/') {
      document.cookie = 'csrftoken=token-inicial; path=/'
      return responder({ codigo: 'OK', csrf_token: 'token-inicial' })
    }

    if (ruta === '/api/auth/login/') {
      if (tokenDe(opciones) !== 'token-inicial') {
        return responder({ codigo: 'CSRF_INVALIDO', mensaje: 'Falta el token CSRF.' }, 403)
      }
      const { email, contrasena } = JSON.parse(opciones.body)
      // Primero las credenciales; solo si son correctas se mira el ambito.
      if (contrasena !== CONTRASENA || email !== emailValido) {
        return responder(
          { codigo: 'CREDENCIALES_INVALIDAS', mensaje: 'Email o contrasena incorrectos.' },
          401,
        )
      }
      if (!perfilDevuelto) {
        // El backend no abre sesion a quien no tiene membresias activas.
        return responder(
          { codigo: 'SIN_AMBITO', mensaje: 'El usuario no tiene membresias activas.' },
          403,
        )
      }
      sesion = perfilDevuelto
      // `django_login` rota el token para defenderse de la fijacion de sesion.
      document.cookie = 'csrftoken=token-tras-login; path=/'
      return responder({ codigo: 'OK', usuario: sesion })
    }

    if (ruta === '/api/auth/me/') {
      if (!sesion) {
        return responder({ codigo: 'NO_AUTENTICADO', mensaje: 'Debe iniciar sesion.' }, 401)
      }
      return responder(sesion)
    }

    if (ruta === '/api/auth/logout/') {
      if (tokenDe(opciones) !== 'token-tras-login') {
        return responder({ codigo: 'CSRF_INVALIDO', mensaje: 'Falta el token CSRF.' }, 403)
      }
      sesion = null
      document.cookie = 'csrftoken=token-tras-logout; path=/'
      return responder({ codigo: 'OK', mensaje: 'Sesion cerrada.' })
    }

    return responder({ codigo: 'NO_ENCONTRADO', mensaje: 'Ruta no implementada.' }, 404)
  })

  vi.stubGlobal('fetch', fake)
  return { peticiones }
}

/**
 * Deja que se resuelva todo lo pendiente.
 *
 * Las vistas se cargan con `import()` dinamico, que no se resuelve en una
 * microtarea: `flushPromises()` solo no alcanza y la navegacion parece no
 * avanzar. Alterna ambos.
 */
async function asentar() {
  for (let vuelta = 0; vuelta < 6; vuelta += 1) {
    await flushPromises()
    await new Promise((resolver) => setTimeout(resolver, 0))
  }
}

/** Levanta la app completa y devuelve los ayudantes para manejarla. */
async function montarApp() {
  const pinia = createPinia()
  const router = createRouter({ history: createWebHistory(), routes: rutas })
  router.beforeEach(crearGuardaSesion({ useAuth: () => useAuthStore(pinia) }))

  const app = mount(App, { global: { plugins: [pinia, router] } })
  await router.isReady()
  await asentar()

  return { app, router, store: useAuthStore(pinia) }
}

/** Rellena y envia el formulario de login. */
async function ingresar(app, { email, contrasena = CONTRASENA } = {}) {
  const campos = app.findAll('input')
  await campos[0].setValue(email)
  await campos[1].setValue(contrasena)
  await app.find('form').trigger('submit')
  await asentar()
}

beforeEach(() => {
  // El cliente memoriza el token CSRF entre pruebas: hay que devolverlo a
  // cero, igual que la cookie, para no arrastrar el de la prueba anterior.
  olvidarTokenCsrf()
  document.cookie = 'csrftoken=; path=/; max-age=0'
})

afterEach(() => {
  olvidarTokenCsrf()
  vi.unstubAllGlobals()
})

describe('proteccion de rutas', () => {
  it('manda al login a quien abre una ruta protegida sin sesion', async () => {
    crearBackend({ perfil: perfilDueno() })
    const { router } = await montarApp()

    await router.push('/panel/acceso')
    await asentar()

    expect(router.currentRoute.value.name).toBe('login')
    // Se recuerda el destino para volver a el despues de entrar.
    expect(router.currentRoute.value.query.next).toBe('/panel/acceso')
  })

  it('no bloquea una ruta abierta', async () => {
    crearBackend({ perfil: perfilDueno() })
    const { router } = await montarApp()

    await router.push('/login')
    await asentar()

    expect(router.currentRoute.value.name).toBe('login')
  })

  it('deja entrar a quien refresca con la sesion viva', async () => {
    // El navegador llega con la cookie de sesion puesta: `me` responde 200.
    const backend = crearBackend({ perfil: perfilDueno(), sesionActiva: true })
    const { router, store } = await montarApp()

    await router.push('/panel/acceso')
    await asentar()

    expect(router.currentRoute.value.name).toBe('acceso')
    expect(store.autenticado).toBe(true)
    // No hace falta volver a preguntar: el login ya habia entregado el perfil.
    expect(backend.peticiones.filter((p) => p.ruta === '/api/auth/login/')).toHaveLength(0)
  })
})

describe('login y sesion', () => {
  it('entra, guarda el perfil y vuelve a la ruta pedida', async () => {
    crearBackend({ perfil: perfilDueno() })
    const { app, router, store } = await montarApp()

    await router.push('/panel/acceso')
    await asentar()
    await ingresar(app, { email: 'dueno@prueba.test' })

    expect(router.currentRoute.value.name).toBe('acceso')
    expect(store.autenticado).toBe(true)
    expect(store.roles).toEqual(['DUENO'])
    expect(app.text()).toContain('dueno@prueba.test')
  })

  it('va al panel si no habia destino guardado', async () => {
    crearBackend({ perfil: perfilDueno() })
    const { app, router } = await montarApp()

    await router.push('/login')
    await asentar()
    await ingresar(app, { email: 'dueno@prueba.test' })

    expect(router.currentRoute.value.name).toBe('panel')
  })

  it('muestra el mensaje del backend cuando las credenciales no sirven', async () => {
    crearBackend({ perfil: perfilDueno() })
    const { app, router, store } = await montarApp()

    await router.push('/login')
    await asentar()
    await ingresar(app, { email: 'dueno@prueba.test', contrasena: 'incorrecta' })

    expect(router.currentRoute.value.name).toBe('login')
    expect(store.autenticado).toBe(false)
    expect(app.text()).toContain('Email o contrasena incorrectos.')
  })

  it('distingue "sin membresias" de "credenciales invalidas"', async () => {
    // Credenciales correctas, pero sin ninguna membresia activa.
    crearBackend({ perfil: null, emailValido: 'huerfano@prueba.test' })
    const { app, router, store } = await montarApp()

    await router.push('/login')
    await asentar()
    await ingresar(app, { email: 'huerfano@prueba.test' })

    expect(store.autenticado).toBe(false)
    expect(router.currentRoute.value.name).toBe('login')
    expect(app.text()).toContain('no tiene membresias activas')
    // El mensaje del backend se muestra tal cual, sin inventar uno propio.
    expect(app.text()).not.toContain('Email o contrasena incorrectos.')
  })
})

describe('la navegacion sigue a los permisos del backend', () => {
  it('un Dueno ve las cuatro secciones pendientes', async () => {
    crearBackend({ perfil: perfilDueno() })
    const { app, router } = await montarApp()

    await router.push('/login')
    await asentar()
    await ingresar(app, { email: 'dueno@prueba.test' })

    const pendientes = app.findAll('li').map((li) => li.text())
    for (const seccion of ['Negocios', 'Sucursales', 'Usuarios', 'Membresias']) {
      expect(pendientes.some((t) => t.includes(seccion))).toBe(true)
    }
  })

  it('un Cajero ve solo las secciones que el backend le devolvio', async () => {
    crearBackend({ perfil: perfilCajero() })
    const { app, router, store } = await montarApp()

    await router.push('/login')
    await asentar()
    await ingresar(app, { email: 'cajero@prueba.test' })

    // Lo que el backend no devolvio, no se dibuja.
    expect(store.tiene('cuentas.view_membresia')).toBe(false)
    expect(store.tiene('cuentas.add_usuario')).toBe(false)

    const pendientes = app.findAll('li').map((li) => li.text())
    expect(pendientes.some((t) => t.includes('Negocios'))).toBe(true)
    expect(pendientes.some((t) => t.includes('Sucursales'))).toBe(true)
    expect(pendientes.some((t) => t.includes('Usuarios'))).toBe(true)
    // Membresias requiere `cuentas.view_membresia`, que el Cajero no tiene.
    expect(pendientes.some((t) => t.includes('Membresias'))).toBe(false)
  })

  it('"Mi acceso" lista exactamente los permisos que devolvio el backend', async () => {
    crearBackend({ perfil: perfilCajero() })
    const { app, router } = await montarApp()

    await router.push('/login')
    await asentar()
    await ingresar(app, { email: 'cajero@prueba.test' })
    await router.push('/panel/acceso')
    await asentar()

    const texto = app.text()
    for (const permiso of PERMISOS_CAJERO) {
      expect(texto).toContain(permiso)
    }
    // Ningun permiso exclusivo del Dueno puede aparecer en la pantalla de un
    // Cajero: la unica fuente es la lista que devolvio `me`.
    for (const permiso of PERMISOS_DUENO.filter((p) => !PERMISOS_CAJERO.includes(p))) {
      expect(texto).not.toContain(permiso)
    }
  })
})

describe('logout', () => {
  it('cierra la sesion y vuelve al login', async () => {
    const backend = crearBackend({ perfil: perfilDueno() })
    const { app, router, store } = await montarApp()

    await router.push('/login')
    await asentar()
    await ingresar(app, { email: 'dueno@prueba.test' })
    expect(store.autenticado).toBe(true)

    const salir = app.findAll('button').find((b) => b.text() === 'Salir')
    await salir.trigger('click')
    await asentar()

    const logout = backend.peticiones.filter((p) => p.ruta === '/api/auth/logout/')
    expect(logout).toHaveLength(1)
    // El logout va con el token que rotó el login, no con el de antes de entrar.
    expect(logout[0].token).toBe('token-tras-login')
    expect(store.autenticado).toBe(false)
    expect(router.currentRoute.value.name).toBe('login')
  })

  it('tras salir, la ruta protegida vuelve a estar cerrada', async () => {
    crearBackend({ perfil: perfilDueno() })
    const { app, router, store } = await montarApp()

    await router.push('/login')
    await asentar()
    await ingresar(app, { email: 'dueno@prueba.test' })

    const salir = app.findAll('button').find((b) => b.text() === 'Salir')
    await salir.trigger('click')
    await asentar()

    await router.push('/panel')
    await asentar()

    expect(store.autenticado).toBe(false)
    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query.next).toBe('/panel')
  })
})