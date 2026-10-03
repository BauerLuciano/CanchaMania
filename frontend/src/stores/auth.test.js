/**
 * Tests del store de sesion.
 *
 * La prueba central es `tiene()`: el frontend no puede concederse un permiso que
 * el backend no devolvio. Eso incluye no abrirle un atajo al superadmin: si el
 * backend no listo el permiso, el panel no lo muestra.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import * as authApi from '../api/authApi.js'
import { obtenerTokenCsrf } from '../api/client.js'
import { useAuthStore } from './auth.js'

vi.mock('../api/authApi.js', () => ({
  RUTAS_AUTH: {},
  pedirTokenCsrf: vi.fn(),
  entrar: vi.fn(),
  salir: vi.fn(),
  perfilActual: vi.fn(),
  catalogoRoles: vi.fn(),
}))

vi.mock('../api/client.js', () => ({
  obtenerTokenCsrf: vi.fn(async () => 'token-nuevo'),
}))

/** Perfil tal como lo devuelve el backend. */
function perfil({
  email = 'cajero@negocio.test',
  permisos = ['cuentas.view_usuario', 'cuentas.view_membresia'],
  roles = ['CAJERO'],
  esSuperadmin = false,
} = {}) {
  return {
    id: 7,
    email,
    nombre: 'Carla Cajero',
    es_superadmin: esSuperadmin,
    roles,
    ambitos: [{ negocio_id: 1, sucursal_id: 2, rol: 'CAJERO', ambito: 'sucursal' }],
    negocios: [
      { id: 1, todo_el_negocio: false, roles: ['CAJERO'], sucursales: [{ id: 2, roles: ['CAJERO'] }] },
    ],
    sucursales: [{ id: 2, roles: ['CAJERO'], negocio_id: 1 }],
    permisos,
  }
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('tiene(): el frontend no concede permisos', () => {
  it('acepta solo los permisos que devolvio el backend', () => {
    const auth = useAuthStore()
    auth.perfil = perfil()

    expect(auth.tiene('cuentas.view_usuario')).toBe(true)
    expect(auth.tiene('cuentas.view_membresia')).toBe(true)
  })

  it('rechaza un permiso que el backend no devolvio', () => {
    const auth = useAuthStore()
    auth.perfil = perfil()

    expect(auth.tiene('cuentas.add_usuario')).toBe(false)
    expect(auth.tiene('cuentas.change_usuario')).toBe(false)
    expect(auth.tiene('sucursales.delete_sucursal')).toBe(false)
  })

  it('no abre un atajo para el superadmin si el backend no listo el permiso', () => {
    const auth = useAuthStore()
    auth.perfil = perfil({ permisos: [], esSuperadmin: true })

    // El backend si le devuelve todos los permisos reales a un superadmin, asi
    // que un perfil vacio con `es_superadmin` solo puede venir de una
    // inconsistencia. El frontend no la compensa inventando permisos.
    expect(auth.esSuperadmin).toBe(true)
    expect(auth.tiene('cuentas.view_usuario')).toBe(false)
    expect(auth.permisos.size).toBe(0)
  })

  it('rechaza entradas invalidas sin fallar', () => {
    const auth = useAuthStore()
    auth.perfil = perfil()

    expect(auth.tiene('')).toBe(false)
    expect(auth.tiene(null)).toBe(false)
    expect(auth.tiene(undefined)).toBe(false)
    expect(auth.tiene(42)).toBe(false)
    expect(auth.tiene({})).toBe(false)
  })

  it('no concede nada sin sesion', () => {
    const auth = useAuthStore()

    expect(auth.autenticado).toBe(false)
    expect(auth.tiene('cuentas.view_usuario')).toBe(false)
    expect(auth.tieneAlcanceTotal()).toBe(false)
  })

  it('tieneAlguno() exige al menos uno y tolera una lista vacia', () => {
    const auth = useAuthStore()
    auth.perfil = perfil()

    expect(auth.tieneAlguno(['cuentas.add_usuario', 'cuentas.view_usuario'])).toBe(true)
    expect(auth.tieneAlguno(['cuentas.add_usuario'])).toBe(false)
    expect(auth.tieneAlguno([])).toBe(false)
    expect(auth.tieneAlguno(undefined)).toBe(false)
  })
})

describe('restaurar()', () => {
  it('carga el perfil y deja la app inicializada', async () => {
    authApi.perfilActual.mockResolvedValue(perfil())
    const auth = useAuthStore()

    await auth.restaurar()

    expect(auth.inicializado).toBe(true)
    expect(auth.autenticado).toBe(true)
    expect(auth.roles).toEqual(['CAJERO'])
  })

  it('un 401 no es un fallo: se sigue sin sesion', async () => {
    const error = new Error('Debe iniciar sesion.')
    error.codigo = 'NO_AUTENTICADO'
    error.estado = 401
    error.sesionCaida = true
    authApi.perfilActual.mockRejectedValue(error)
    const auth = useAuthStore()

    await auth.restaurar()

    expect(auth.inicializado).toBe(true)
    expect(auth.autenticado).toBe(false)
    expect(auth.error).toBeNull()
  })

  it('un error de red deja la app inicializada igual, para no trabar la navegacion', async () => {
    const error = new Error('Sin conexion.')
    error.estado = 0
    authApi.perfilActual.mockRejectedValue(error)
    const auth = useAuthStore()

    await auth.restaurar()

    expect(auth.inicializado).toBe(true)
    expect(auth.autenticado).toBe(false)
    expect(auth.error).toBe(error)
  })

  it('no vuelve a pedir el perfil si ya esta inicializado', async () => {
    authApi.perfilActual.mockResolvedValue(perfil())
    const auth = useAuthStore()

    await auth.restaurar()
    await auth.restaurar()

    expect(authApi.perfilActual).toHaveBeenCalledTimes(1)
  })

  it('las llamadas concurrentes comparten una sola peticion', async () => {
    authApi.perfilActual.mockResolvedValue(perfil())
    const auth = useAuthStore()

    await Promise.all([auth.restaurar(), auth.restaurar(), auth.restaurar()])

    expect(authApi.perfilActual).toHaveBeenCalledTimes(1)
  })
})

describe('ingresar()', () => {
  it('guarda el perfil que devuelve el login, sin pedir un me extra', async () => {
    authApi.entrar.mockResolvedValue({
      codigo: 'OK',
      usuario: perfil({ email: 'dueno@negocio.test', roles: ['DUENO'] }),
    })
    const auth = useAuthStore()

    const resultado = await auth.ingresar({ email: 'dueno@negocio.test', contrasena: 'Clave1!' })

    expect(resultado.email).toBe('dueno@negocio.test')
    expect(auth.autenticado).toBe(true)
    expect(auth.tiene('cuentas.view_usuario')).toBe(true)
    expect(authApi.perfilActual).not.toHaveBeenCalled()
  })

  it('propaga el error del backend para que la pantalla lo muestre', async () => {
    const error = new Error('Email o contrasena incorrectos.')
    error.codigo = 'CREDENCIALES_INVALIDAS'
    authApi.entrar.mockRejectedValue(error)
    const auth = useAuthStore()

    await expect(auth.ingresar({ email: 'x@y.test', contrasena: 'z' })).rejects.toBe(error)
    expect(auth.autenticado).toBe(false)
    expect(auth.error).toBe(error)
    expect(auth.ocupado).toBe(false)
  })

  it('propaga SIN_AMBITO: el backend no abre sesion sin membresias', async () => {
    const error = new Error('El usuario no tiene membresias activas en ningun negocio.')
    error.codigo = 'SIN_AMBITO'
    authApi.entrar.mockRejectedValue(error)
    const auth = useAuthStore()

    await expect(auth.ingresar({ email: 'x@y.test', contrasena: 'z' })).rejects.toMatchObject({
      codigo: 'SIN_AMBITO',
    })
    expect(auth.autenticado).toBe(false)
  })
})

describe('cerrar()', () => {
  it('cierra sesion y pide un token CSRF nuevo', async () => {
    authApi.perfilActual.mockResolvedValue(perfil())
    authApi.salir.mockResolvedValue({ codigo: 'OK' })
    const auth = useAuthStore()
    await auth.restaurar()

    await auth.cerrar()

    expect(authApi.salir).toHaveBeenCalledTimes(1)
    expect(auth.autenticado).toBe(false)
    // django_logout rota el token del servidor: el viejo ya no sirve.
    expect(obtenerTokenCsrf).toHaveBeenCalledWith({ forzar: true })
  })

  it('limpia el estado local aunque el backend falle', async () => {
    authApi.perfilActual.mockResolvedValue(perfil())
    authApi.salir.mockRejectedValue(new Error('Sin conexion.'))
    const auth = useAuthStore()
    await auth.restaurar()

    await auth.cerrar()

    expect(auth.autenticado).toBe(false)
    expect(auth.error).toBeInstanceOf(Error)
  })
})

describe('olvidarLocal()', () => {
  it('descarta la sesion sin pegarle al backend y refresca el token', async () => {
    authApi.perfilActual.mockResolvedValue(perfil())
    const auth = useAuthStore()
    await auth.restaurar()

    await auth.olvidarLocal()

    expect(auth.autenticado).toBe(false)
    expect(authApi.salir).not.toHaveBeenCalled()
    expect(obtenerTokenCsrf).toHaveBeenCalledWith({ forzar: true })
  })

  it('no deja la app sin inicializar si el token no se puede renovar', async () => {
    obtenerTokenCsrf.mockRejectedValueOnce(new Error('Sin conexion.'))
    authApi.perfilActual.mockResolvedValue(perfil())
    const auth = useAuthStore()
    await auth.restaurar()

    await expect(auth.olvidarLocal()).resolves.toBeUndefined()
    expect(auth.autenticado).toBe(false)
    expect(auth.inicializado).toBe(true)
  })
})
