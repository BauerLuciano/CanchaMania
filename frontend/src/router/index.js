/**
 * Router de la SPA.
 *
 * `createWebHistory` porque Django sirve la app con una ruta catch-all
 * (`config/urls.py`) y cualquier URL profunda tiene que resolver al index.
 */
import { createRouter, createWebHistory } from 'vue-router'
import { createPinia } from 'pinia'

import { crearGuardaSesion } from './guard.js'
import rutas from './rutas.js'
import { useAuthStore } from '../stores/auth.js'

export function crearRouter(pinia = createPinia()) {
  const router = createRouter({
    history: createWebHistory(),
    routes: rutas,
    scrollBehavior: () => ({ top: 0 }),
  })

  router.beforeEach(
    crearGuardaSesion({
      // El store se resuelve con la instancia de Pinia de la app: asi la guarda
      // y los componentes comparten exactamente el mismo estado.
      useAuth: () => useAuthStore(pinia),
    }),
  )

  router.afterEach((to) => {
    const titulo = to.meta?.titulo
    document.title = titulo ? `${titulo} - CanchaMania` : 'CanchaMania'
  })

  return router
}

export default crearRouter
