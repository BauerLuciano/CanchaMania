/**
 * Tests del cliente HTTP.
 *
 * Lo que se verifica aca es lo que el resto de la aplicacion da por sentado:
 * que la sesion viaje siempre, que CSRF se pida y se mande, y que todo error
 * llegue ya normalizado como `ApiError` con el codigo del backend.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

/** Carga una instancia nueva del modulo para partir del token CSRF vacio. */
async function clienteLimpio() {
  vi.resetModules()
  return import('./client.js')
}

/** Respuesta minima con la forma que el cliente consume. */
function respuesta(cuerpo, estado = 200) {
  return {
    ok: estado >= 200 && estado < 300,
    status: estado,
    text: async () => (cuerpo === undefined ? '' : JSON.stringify(cuerpo)),
  }
}

/** Ruta del token CSRF, en el origen de jsdom. */
const ORIGEN = 'http://localhost:3000'
const PATH_CSRF = '/api/auth/csrf/'

/** Respuesta por defecto del endpoint de CSRF. */
const RESPUESTA_CSRF = { codigo: 'OK', csrf_token: 'token-abc' }

/**
 * Stub de fetch que responde por ruta y registra las llamadas.
 *
 * Indexa por `pathname` y no por URL completa, para no tener que adivinar el
 * query string en cada caso. `GET /api/auth/csrf/` esta stubbeado siempre salvo
 * que el test lo sobreescriba: asi cada test declara solo las rutas que le
 * importan y los POST igual tienen token.
 *
 * Reemplaza el global y deja `llamadas` apuntando al registro nuevo.
 */
function stubFetch(tabla = {}) {
  const registro = []
  const fake = vi.fn(async (url, opciones = {}) => {
    const ruta = String(url)
    registro.push({ ruta, ...opciones })

    const path = new URL(ruta, ORIGEN).pathname
    if (path === PATH_CSRF && !(path in tabla)) return respuesta(RESPUESTA_CSRF)

    const encontrado = tabla[path]
    const salida = typeof encontrado === 'function' ? encontrado(opciones) : encontrado
    return salida ?? respuesta({ codigo: 'NO_ENCONTRADO', mensaje: 'Sin stub.' }, 404)
  })
  // `stubGlobal` y no una asignacion directa: Vitest sabe deshacerlo al
  // terminar el test, y asi un stub no se filtra al siguiente.
  vi.stubGlobal('fetch', fake)
  llamadas = registro
  return registro
}

/** Reemplaza `fetch` por uno que siempre falla a nivel de red. */
function stubFetchQueFalla() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => {
      throw new TypeError('Failed to fetch')
    }),
  )
}

let llamadas

beforeEach(() => {
  stubFetch()
  document.cookie = 'csrftoken=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT'
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('sesion', () => {
  it('manda las credenciales en toda peticion, para que viaje la cookie de sesion', async () => {
    stubFetch({ '/api/auth/me/': respuesta({ id: 1 }) })
    const { api } = await clienteLimpio()

    await api.get('/auth/me/')

    expect(llamadas).toHaveLength(1)
    expect(llamadas[0].credentials).toBe('include')
  })
})

describe('CSRF', () => {
  it('no pide token ni manda cabecera en los metodos seguros', async () => {
    stubFetch({ '/api/auth/me/': respuesta({ id: 1 }) })
    const { api } = await clienteLimpio()

    await api.get('/auth/me/')

    expect(llamadas.map((c) => c.ruta)).toEqual([`${ORIGEN}/api/auth/me/`])
    expect(llamadas[0].headers['X-CSRFToken']).toBeUndefined()
  })

  it('pide el token a /auth/csrf/ antes de la primera escritura y lo manda', async () => {
    stubFetch({ '/api/auth/login/': respuesta({ codigo: 'OK' }) })
    const { api } = await clienteLimpio()

    await api.post('/auth/login/', { email: 'a@b.test', contrasena: 'x' })

    expect(llamadas.map((c) => c.ruta)).toEqual([
      `${ORIGEN}/api/auth/csrf/`,
      `${ORIGEN}/api/auth/login/`,
    ])
    expect(llamadas[1].headers['X-CSRFToken']).toBe('token-abc')
    expect(llamadas[1].headers['Content-Type']).toBe('application/json')
  })

  it('reutiliza el token en las escrituras siguientes', async () => {
    stubFetch({
      '/api/auth/login/': respuesta({ codigo: 'OK' }),
      '/api/auth/logout/': respuesta({ codigo: 'OK' }),
    })
    const { api } = await clienteLimpio()

    await api.post('/auth/login/', { email: 'a@b.test' })
    await api.post('/auth/logout/')

    expect(llamadas.filter((c) => c.ruta.endsWith('/auth/csrf/'))).toHaveLength(1)
  })

  it('comparte una sola peticion de token entre escrituras concurrentes', async () => {
    stubFetch({
      '/api/auth/login/': respuesta({ codigo: 'OK' }),
      '/api/membresias/': respuesta({ codigo: 'OK' }),
    })
    const { api } = await clienteLimpio()

    await Promise.all([
      api.post('/auth/login/', { email: 'a@b.test' }),
      api.post('/membresias/', {}),
    ])

    expect(llamadas.filter((c) => c.ruta.endsWith('/auth/csrf/'))).toHaveLength(1)
  })

  it('usa el token de la cookie sin pedirlo al servidor', async () => {
    stubFetch({
      '/api/auth/csrf/': respuesta({ codigo: 'OK', csrf_token: 'token-del-cuerpo' }),
      '/api/auth/login/': respuesta({ codigo: 'OK' }),
    })
    document.cookie = 'csrftoken=token-de-cookie; path=/'
    const { api } = await clienteLimpio()

    await api.post('/auth/login/', {})

    // La cookie es la fuente de verdad: no hace falta ni una peticion extra.
    expect(llamadas).toHaveLength(1)
    expect(llamadas[0].ruta).toContain('/api/auth/login/')
    expect(llamadas[0].headers['X-CSRFToken']).toBe('token-de-cookie')
  })

  it('descarta el token tras un CSRF_INVALIDO y pide uno nuevo en el reintento', async () => {
    let intentos = 0
    stubFetch({
      '/api/auth/csrf/': (opciones) =>
        opciones.method === 'GET'
          ? respuesta({ codigo: 'OK', csrf_token: `token-${++intentos}` })
          : respuesta({ codigo: 'X' }, 400),
      '/api/auth/login/': () =>
        intentos === 1
          ? respuesta({ codigo: 'CSRF_INVALIDO', mensaje: 'CSRF verificado fallido.' }, 403)
          : respuesta({ codigo: 'OK' }),
    })
    const { api } = await clienteLimpio()

    await expect(api.post('/auth/login/', {})).rejects.toMatchObject({ codigo: 'CSRF_INVALIDO' })
    await expect(api.post('/auth/login/', {})).resolves.toMatchObject({ codigo: 'OK' })

    expect(llamadas.filter((c) => c.ruta.endsWith('/auth/csrf/'))).toHaveLength(2)
  })

  it('forzar el token lo vuelve a pedir aunque ya haya uno', async () => {
    const { obtenerTokenCsrf } = await clienteLimpio()

    const primero = await obtenerTokenCsrf()
    const segundo = await obtenerTokenCsrf({ forzar: true })

    expect(primero).toBe('token-abc')
    expect(segundo).toBe('token-abc')
    expect(llamadas.filter((c) => c.ruta.endsWith('/auth/csrf/'))).toHaveLength(2)
  })

  it('usa el token que el servidor rotó al iniciar sesión, no el anterior', async () => {
    stubFetch({
      '/api/auth/login/': respuesta({ codigo: 'OK' }),
      '/api/auth/logout/': respuesta({ codigo: 'OK' }),
    })
    // El token se pide antes de entrar y queda en la cookie.
    document.cookie = 'csrftoken=token-antes-del-login; path=/'
    const { api } = await clienteLimpio()

    await api.post('/auth/login/', {})

    // Django rota el secreto CSRF en cada login() y deja la cookie nueva.
    // Reusar el token previo haria fallar esta escritura.
    document.cookie = 'csrftoken=token-rotado-por-el-login; path=/'
    await api.post('/auth/logout/')

    expect(llamadas[0].headers['X-CSRFToken']).toBe('token-antes-del-login')
    expect(llamadas[1].headers['X-CSRFToken']).toBe('token-rotado-por-el-login')
    // Con la cookie presente no hace falta pedir el token: se lee de ahi.
    expect(llamadas.filter((c) => c.ruta.endsWith('/auth/csrf/'))).toHaveLength(0)
  })

  it('descarta la cookie tras un CSRF_INVALIDO para poder pedir uno nuevo de verdad', async () => {
    let intento = 0
    stubFetch({
      '/api/auth/csrf/': respuesta({ codigo: 'OK', csrf_token: 'token-nuevo' }),
      // El servidor rechaza la primera escritura y acepta la segunda.
      '/api/auth/login/': () =>
        ++intento === 1
          ? respuesta({ codigo: 'CSRF_INVALIDO', mensaje: 'Falta el token CSRF.' }, 403)
          : respuesta({ codigo: 'OK' }),
    })
    document.cookie = 'csrftoken=token-vencido; path=/'
    const { api } = await clienteLimpio()

    await expect(api.post('/auth/login/', {})).rejects.toMatchObject({ codigo: 'CSRF_INVALIDO' })
    await expect(api.post('/auth/login/', {})).resolves.toMatchObject({ codigo: 'OK' })

    // La cookie vencida se descarta, asi que el reintento tiene que pedir un
    // token nuevo al servidor en vez de reusar el que ya habia sido rechazado.
    expect(llamadas[0].headers['X-CSRFToken']).toBe('token-vencido')
    expect(llamadas.filter((c) => c.ruta.endsWith('/auth/csrf/'))).toHaveLength(1)
    expect(llamadas[llamadas.length - 1].headers['X-CSRFToken']).toBe('token-nuevo')
  })
})

describe('normalizacion de errores', () => {
  it('arma un ApiError con el codigo y el mensaje del backend', async () => {
    stubFetch({
      '/api/auth/login/': respuesta(
        { codigo: 'CREDENCIALES_INVALIDAS', mensaje: 'Email o contrasena incorrectos.' },
        401,
      ),
    })
    const { api } = await clienteLimpio()

    const error = await api.post('/auth/login/', {}).catch((e) => e)

    expect(error.name).toBe('ApiError')
    expect(error.codigo).toBe('CREDENCIALES_INVALIDAS')
    expect(error.mensaje).toBe('Email o contrasena incorrectos.')
    expect(error.estado).toBe(401)
    expect(error.sesionCaida).toBe(true)
  })

  it('deja los errores por campo en detalles y permite consultarlos', async () => {
    stubFetch({
      '/api/usuarios/': respuesta(
        {
          codigo: 'VALIDACION_INVALIDA',
          mensaje: 'Los datos enviados no son validos.',
          detalles: { email: ['Ya existe un usuario con ese email.'], nombre: 'Obligatorio.' },
        },
        400,
      ),
    })
    const { api } = await clienteLimpio()

    const error = await api.post('/usuarios/', {}).catch((e) => e)

    expect(error.validacion).toBe(true)
    expect(error.errorDe('email')).toBe('Ya existe un usuario con ese email.')
    expect(error.errorDe('nombre')).toBe('Obligatorio.')
    expect(error.errorDe('apellido')).toBeNull()
  })

  it('avisa a los escuchadores cuando la sesion deja de existir', async () => {
    stubFetch({ '/api/negocios/': respuesta({ codigo: 'NO_AUTENTICADO' }, 401) })
    const { api, alCaerLaSesion } = await clienteLimpio()
    const oyente = vi.fn()
    alCaerLaSesion(oyente)

    await expect(api.get('/negocios/')).rejects.toMatchObject({ codigo: 'NO_AUTENTICADO' })

    expect(oyente).toHaveBeenCalledTimes(1)
  })

  it('deja de avisar cuando se da de baja el escuchador', async () => {
    stubFetch({ '/api/negocios/': respuesta({ codigo: 'NO_AUTENTICADO' }, 401) })
    const { api, alCaerLaSesion } = await clienteLimpio()
    const oyente = vi.fn()
    alCaerLaSesion(oyente)()

    await api.get('/negocios/').catch(() => {})

    expect(oyente).not.toHaveBeenCalled()
  })

  it('traduce un cuerpo que no es JSON en vez de propagarlo', async () => {
    stubFetch({
      '/api/auth/me/': {
        ok: false,
        status: 502,
        text: async () => '<html>Bad Gateway</html>',
      },
    })
    const { api } = await clienteLimpio()

    const error = await api.get('/auth/me/').catch((e) => e)

    expect(error.codigo).toBe('ERROR_INTERNO')
    expect(error.estado).toBe(502)
  })

  it('distingue un fallo de red de un error del backend', async () => {
    stubFetchQueFalla()
    const { api, ERROR_DE_RED } = await clienteLimpio()

    const error = await api.get('/auth/me/').catch((e) => e)

    expect(error.codigo).toBe(ERROR_DE_RED)
    expect(error.estado).toBe(0)
  })

  it('devuelve null en un 204 en lugar de fallar al parsear', async () => {
    stubFetch({ '/api/usuarios/1/': respuesta(undefined, 204) })
    const { api } = await clienteLimpio()

    await expect(api.delete('/usuarios/1/')).resolves.toBeNull()
  })
})

describe('urls', () => {
  it('acepta la ruta con o sin slash inicial', async () => {
    stubFetch({ '/api/auth/me/': respuesta({ id: 1 }) })
    const { api } = await clienteLimpio()

    await api.get('auth/me/')

    expect(llamadas[0].ruta).toBe(`${ORIGEN}/api/auth/me/`)
  })

  it('arma el query string omitiendo los parametros vacios', async () => {
    stubFetch({ '/api/sucursales/': respuesta({ results: [] }) })
    const { api } = await clienteLimpio()

    await api.get('/sucursales/', { params: { page: 2, page_size: '', busqueda: null } })

    expect(llamadas[0].ruta).toBe(`${ORIGEN}/api/sucursales/?page=2`)
  })
})
