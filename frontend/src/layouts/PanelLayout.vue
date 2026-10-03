<script setup>
/**
 * Layout del panel: barra lateral + cabecera + contenido.
 *
 * La barra lateral se arma desde `config/navegacion.js` y se filtra con los
 * permisos que devolvio `/api/auth/me/`. Dos reglas:
 *
 * 1. Una seccion sin permiso del backend no se dibuja.
 * 2. La seccion del superadmin tambien pasa por el filtro: el backend le
 *    devuelve todos los permisos reales, asi que no hace falta ningun caso
 *    especial aqui.
 *
 * La sesion va en la cabecera porque el menu lateral es donde se navega, no
 * donde se sale.
 */
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { SECCIONES, SECCIONES_PENDIENTES } from '../config/navegacion.js'
import { useAuthStore } from '../stores/auth.js'
import AlertaMensaje from '../components/ui/AlertaMensaje.vue'
import BotonUi from '../components/ui/BotonUi.vue'
import InsigniaUi from '../components/ui/InsigniaUi.vue'

const auth = useAuthStore()
const router = useRouter()
const { perfil, nombreMostrado, iniciales, roles } = storeToRefs(auth)

const menuAbierto = ref(false)
const errorSalir = ref(null)

/** Secciones de esta etapa que el backend habilita. */
const seccionesVisibles = computed(() =>
  SECCIONES.filter((seccion) => !seccion.permiso || auth.tiene(seccion.permiso)),
)

/**
 * Secciones de etapas siguientes que el backend habilita.
 *
 * Se listan bloqueadas: dicen que falta la pantalla, no que falte el permiso.
 * Si el permiso tampoco esta, la seccion no aparece.
 */
const seccionesPendientes = computed(() =>
  SECCIONES_PENDIENTES.filter((seccion) => auth.tiene(seccion.permiso)),
)

const tonoDeRol = (rol) =>
  ({ DUENO: 'dueno', ENCARGADO: 'encargado', CAJERO: 'cajero' })[rol] ?? 'neutro'

async function cerrarSesion() {
  errorSalir.value = null
  try {
    await auth.cerrar()
    router.push({ name: 'login' })
  } catch {
    errorSalir.value = 'No se pudo confirmar el cierre de sesion en el servidor.'
  }
}
</script>

<template>
  <div class="min-h-screen lg:flex">
    <!-- Barra lateral -->
    <aside
      class="fixed inset-y-0 left-0 z-30 w-64 shrink-0 border-r border-slate-200 bg-white
        transition-transform lg:static lg:translate-x-0"
      :class="menuAbierto ? 'translate-x-0' : '-translate-x-full'"
      aria-label="Navegacion principal"
    >
      <div class="flex h-16 items-center gap-2 border-b border-slate-200 px-5">
        <RouterLink to="/panel" class="flex items-center gap-2" @click="menuAbierto = false">
          <span
            class="flex size-8 items-center justify-center rounded-lg bg-cancha-700 text-sm font-bold text-white"
            aria-hidden="true"
          >
            CM
          </span>
          <span class="text-base font-semibold tracking-tight text-slate-900">CanchaMania</span>
        </RouterLink>
      </div>

      <nav class="flex flex-col gap-6 overflow-y-auto p-4">
        <div>
          <p class="px-3 pb-2 text-xs font-semibold tracking-wide text-slate-400 uppercase">
            Navegacion
          </p>
          <ul class="flex flex-col gap-1">
            <li v-for="seccion in seccionesVisibles" :key="seccion.id">
              <RouterLink
                :to="seccion.ruta"
                class="block rounded-lg px-3 py-2 text-sm font-medium text-slate-700 transition
                  hover:bg-slate-100 hover:text-slate-900"
                active-class="bg-cancha-50 text-cancha-800"
                @click="menuAbierto = false"
              >
                {{ seccion.titulo }}
              </RouterLink>
            </li>
          </ul>
        </div>

        <div v-if="seccionesPendientes.length">
          <p class="px-3 pb-2 text-xs font-semibold tracking-wide text-slate-400 uppercase">
            Proximas etapas
          </p>
          <ul class="flex flex-col gap-1">
            <li
              v-for="seccion in seccionesPendientes"
              :key="seccion.id"
              class="flex items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm text-slate-400"
              :title="seccion.descripcion"
            >
              <span>{{ seccion.titulo }}</span>
              <span class="text-xs whitespace-nowrap">Pronto</span>
            </li>
          </ul>
          <p class="px-3 pt-2 text-xs text-slate-400">
            Se listan porque el backend habilita su permiso; la pantalla todavia no existe.
          </p>
        </div>
      </nav>
    </aside>

    <!-- Capa oscura al abrir el menu en pantallas chicas -->
    <div
      v-if="menuAbierto"
      class="fixed inset-0 z-20 bg-slate-900/40 lg:hidden"
      @click="menuAbierto = false"
    />

    <div class="flex min-w-0 flex-1 flex-col">
      <!-- Cabecera -->
      <header class="sticky top-0 z-10 border-b border-slate-200 bg-white">
        <div class="flex h-16 items-center gap-3 px-4 sm:px-6">
          <button
            type="button"
            class="rounded-lg p-2 text-slate-500 hover:bg-slate-100 lg:hidden"
            :aria-expanded="menuAbierto"
            aria-label="Abrir navegacion"
            @click="menuAbierto = !menuAbierto"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="size-5">
              <path d="M4 6h16M4 12h16M4 18h16" stroke-linecap="round" />
            </svg>
          </button>

          <h1 class="min-w-0 flex-1 truncate text-sm font-medium text-slate-500">
            {{ $route.meta?.titulo ?? 'CanchaMania' }}
          </h1>

          <div v-if="perfil" class="flex items-center gap-3">
            <div class="hidden text-right sm:block">
              <p class="truncate text-sm font-medium text-slate-900">{{ nombreMostrado }}</p>
              <div class="mt-0.5 flex items-center justify-end gap-1">
                <InsigniaUi
                  v-for="rol in roles"
                  :key="rol"
                  :texto="rol"
                  :tono="tonoDeRol(rol)"
                />
              </div>
            </div>
            <span
              class="flex size-9 shrink-0 items-center justify-center rounded-full bg-cancha-100 text-sm font-semibold text-cancha-800"
              aria-hidden="true"
            >
              {{ iniciales }}
            </span>
            <BotonUi
              variante="fantasma"
              tamano="sm"
              :cargando="auth.ocupado"
              @click="cerrarSesion"
            >
              Salir
            </BotonUi>
          </div>
        </div>
      </header>

      <main class="flex-1 p-4 sm:p-6">
        <AlertaMensaje
          v-if="errorSalir"
          class="mb-4"
          :mensaje="errorSalir"
          @click="errorSalir = null"
        />
        <slot />
      </main>
    </div>
  </div>
</template>
