/**
 * Tests de la guarda de rutas.
 *
 * Se prueba `decidirNavegacion`, que es pura: recibe el estado y devuelve la
 * redireccion. Asi se cubren los casos de proteccion sin montar un router.
 */
import { describe, expect, it } from 'vitest'

import { crearGuardaSesion, decidirNavegacion } from './guard.js'

/** Simula lo que Vue Router entrega a una guarda. */
function ruta({ fullPath = '/panel', name = 'panel', meta = {}, anidados = [] } = {}) {
  const propio = { meta }
  return {
    fullPath,
    name,
    meta,
    matched: [{ meta }, ...anidados.map((metaHijo) => ({ meta: metaHijo }))],
    ...propio,
  }
}

const conTodo = () => true
const conNada = () => false

describe('proteccion de rutas autenticadas', () => {
  it('deja pasar a una ruta abierta', () => {
    const destino = ruta({ name: 'login', fullPath: '/login', meta: { requiereAuth: false } })

    expect(decidirNavegacion({ to: destino, autenticado: false, tiene: conNada })).toBe(true)
  })

  it('manda al login a quien no tiene sesion, recordando el destino', () => {
    const destino = ruta({ fullPath: '/panel/acceso', meta: { requiereAuth: true } })

    const resultado = decidirNavegacion({ to: destino, autenticado: false, tiene: conNada })

    expect(resultado).toEqual({ name: 'login', query: { next: '/panel/acceso' }, replace: true })
  })

  it('no manda al login a quien ya tiene sesion', () => {
    const destino = ruta({ fullPath: '/panel', meta: { requiereAuth: true } })

    expect(decidirNavegacion({ to: destino, autenticado: true, tiene: conNada })).toBe(true)
  })

  it('saca del login a quien ya esta autenticado', () => {
    const destino = ruta({ name: 'login', fullPath: '/login', meta: { requiereAuth: false } })

    expect(decidirNavegacion({ to: destino, autenticado: true, tiene: conNada })).toEqual({
      name: 'panel',
      replace: true,
    })
  })

  it('detecta la proteccion en una ruta anidada, no solo en la propia', () => {
    const destino = ruta({
      fullPath: '/panel/ajustes',
      meta: {},
      anidados: [{ requiereAuth: true }],
    })

    const resultado = decidirNavegacion({ to: destino, autenticado: false, tiene: conNada })

    expect(resultado.name).toBe('login')
  })
})

describe('metadatos de permisos', () => {
  it('deja pasar si el backend devolvio el permiso', () => {
    const destino = ruta({ meta: { requiereAuth: true, permiso: 'cuentas.view_usuario' } })

    expect(
      decidirNavegacion({ to: destino, autenticado: true, tiene: conTodo }),
    ).toBe(true)
  })

  it('bloquea si el backend no devolvio el permiso', () => {
    const destino = ruta({
      fullPath: '/panel/usuarios',
      meta: { requiereAuth: true, permiso: 'cuentas.add_usuario' },
    })

    const resultado = decidirNavegacion({
      to: destino,
      autenticado: true,
      tiene: (p) => p === 'cuentas.view_usuario',
    })

    expect(resultado).toEqual({
      name: 'sin-permiso',
      query: { de: '/panel/usuarios' },
      replace: true,
    })
  })

  it('una ruta con permiso exige sesion aunque no declare requiereAuth', () => {
    const destino = ruta({ fullPath: '/panel/usuarios', meta: { permiso: 'cuentas.add_usuario' } })

    // Sin sesion gana el redirect al login: no tiene sentido preguntar por
    // permisos de un usuario que todavia no existe en el navegador.
    const resultado = decidirNavegacion({ to: destino, autenticado: false, tiene: conNada })

    expect(resultado.name).toBe('login')
  })

  it('una ruta con permiso y sesion va a la pantalla de sin permisos', () => {
    const destino = ruta({ fullPath: '/panel/usuarios', meta: { permiso: 'cuentas.add_usuario' } })

    const resultado = decidirNavegacion({ to: destino, autenticado: true, tiene: conNada })

    expect(resultado.name).toBe('sin-permiso')
  })
})

describe('crearGuardaSesion', () => {
  it('recupera la sesion antes de decidir', async () => {
    const llamadas = []
    const auth = {
      inicializado: false,
      autenticado: true,
      restaurar: async () => {
        llamadas.push('restaurar')
        auth.inicializado = true
      },
      tiene: () => true,
    }
    const guarda = crearGuardaSesion({ useAuth: () => auth })

    const resultado = await guarda(ruta({ meta: { requiereAuth: true } }))

    expect(llamadas).toEqual(['restaurar'])
    expect(resultado).toBe(true)
  })

  it('no vuelve a restaurar si la app ya esta inicializada', async () => {
    let restaura = 0
    const auth = {
      inicializado: true,
      autenticado: false,
      restaurar: async () => {
        restaura += 1
      },
      tiene: () => false,
    }
    const guarda = crearGuardaSesion({ useAuth: () => auth })

    await guarda(ruta({ meta: { requiereAuth: true } }))

    expect(restaura).toBe(0)
  })
})
