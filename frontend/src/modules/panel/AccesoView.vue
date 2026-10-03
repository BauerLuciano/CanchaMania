<script setup>
/**
 * "Mi acceso": la lista literal de lo que el backend devolvio.
 *
 * Es una pantalla de diagnostico y de transparencia: muestra los roles, los
 * ambitos, los negocios y sucursales alcanzables y los permisos efectivos tal
 * cual llegaron de `/api/auth/me/`. No calcula nada.
 *
 * Sirve para verificar de un vistazo que el frontend no se atribuye permisos que
 * el backend no le dio: si algo aparece aca, esta porque vino en el perfil.
 */
import { computed } from 'vue'
import { storeToRefs } from 'pinia'

import { useAuthStore } from '../../stores/auth.js'
import CargandoUi from '../../components/ui/CargandoUi.vue'
import InsigniaUi from '../../components/ui/InsigniaUi.vue'
import TarjetaUi from '../../components/ui/TarjetaUi.vue'

const auth = useAuthStore()
const { perfil, inicializado, roles, permisos, negocios, sucursales, ambitos } = storeToRefs(auth)

const tonoDeRol = (rol) =>
  ({ DUENO: 'dueno', ENCARGADO: 'encargado', CAJERO: 'cajero' })[rol] ?? 'neutro'

/** Permisos agrupados por app, que es como los agrupa el backend. */
const permisosPorApp = computed(() => {
  const grupos = new Map()
  for (const permiso of permisos.value) {
    const [app] = permiso.split('.')
    if (!grupos.has(app)) grupos.set(app, [])
    grupos.get(app).push(permiso)
  }
  return [...grupos.entries()].sort(([a], [b]) => a.localeCompare(b))
})

const ambitoDe = (ambito) =>
  ambito.ambito === 'negocio'
    ? `Negocio ${ambito.negocio_id} (todo el negocio)`
    : `Negocio ${ambito.negocio_id} / Sucursal ${ambito.sucursal_id}`
</script>

<template>
  <CargandoUi v-if="!inicializado" texto="Leyendo tu perfil..." />

  <div v-else-if="perfil" class="flex flex-col gap-6">
    <TarjetaUi titulo="Identidad" :descripcion="`Id ${perfil.id}`">
      <dl class="grid gap-4 sm:grid-cols-2">
        <div>
          <dt class="text-sm text-slate-500">Nombre</dt>
          <dd class="font-medium text-slate-900">{{ perfil.nombre || '—' }}</dd>
        </div>
        <div>
          <dt class="text-sm text-slate-500">Email</dt>
          <dd class="font-medium break-all text-slate-900">{{ perfil.email }}</dd>
        </div>
        <div>
          <dt class="text-sm text-slate-500">Superadmin</dt>
          <dd class="font-medium text-slate-900">{{ perfil.es_superadmin ? 'Si' : 'No' }}</dd>
        </div>
        <div>
          <dt class="text-sm text-slate-500">Roles</dt>
          <dd class="mt-1 flex flex-wrap gap-1">
            <InsigniaUi v-for="rol in roles" :key="rol" :texto="rol" :tono="tonoDeRol(rol)" />
          </dd>
        </div>
      </dl>
    </TarjetaUi>

    <TarjetaUi
      titulo="Ambitos"
      descripcion="Origen de todo lo que podes ver: tus membresias activas."
    >
      <ul v-if="ambitos.length" class="flex flex-col gap-2">
        <li
          v-for="ambito in ambitos"
          :key="`${ambito.negocio_id}-${ambito.sucursal_id}-${ambito.rol}`"
          class="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm"
        >
          <span class="text-slate-800">{{ ambitoDe(ambito) }}</span>
          <InsigniaUi :texto="ambito.rol" :tono="tonoDeRol(ambito.rol)" />
        </li>
      </ul>
      <p v-else class="text-sm text-slate-600">
        No tenes membresias activas. Sin membresias el backend no abre panel.
      </p>

      <dl class="mt-5 grid gap-4 sm:grid-cols-2">
        <div>
          <dt class="text-sm text-slate-500">Negocios alcanzables</dt>
          <dd class="mt-1 text-sm text-slate-800">
            <span v-for="(negocio, i) in negocios" :key="negocio.id">
              {{ negocio.id }}<span class="text-slate-500">{{ negocio.todo_el_negocio ? ' (total)' : '' }}</span><span
                v-if="i < negocios.length - 1"
              >, </span
              >
            </span>
            <span v-if="!negocios.length">—</span>
          </dd>
        </div>
        <div>
          <dt class="text-sm text-slate-500">Sucursales alcanzables</dt>
          <dd class="mt-1 text-sm text-slate-800">
            <span v-for="(sucursal, i) in sucursales" :key="sucursal.id">
              {{ sucursal.id }}<span v-if="i < sucursales.length - 1">, </span>
            </span>
            <span v-if="!sucursales.length">—</span>
          </dd>
        </div>
      </dl>
    </TarjetaUi>

    <TarjetaUi
      titulo="Permisos efectivos"
      :descripcion="`${permisos.size} permisos devueltos por el backend. Son los unicos que el panel usa para decidir que muestra.`"
    >
      <div class="flex flex-col gap-4">
        <div v-for="[app, lista] in permisosPorApp" :key="app">
          <p class="mb-1.5 font-mono text-xs font-semibold text-slate-500">{{ app }}</p>
          <ul class="flex flex-wrap gap-1.5">
            <li v-for="permiso in lista" :key="permiso">
              <code class="rounded bg-slate-100 px-2 py-1 font-mono text-xs text-slate-700">
                {{ permiso }}
              </code>
            </li>
          </ul>
        </div>
      </div>

      <p class="mt-5 border-t border-slate-200 pt-4 text-xs text-slate-500">
        Ocultar una pantalla no es autorizar: cada endpoint del backend vuelve a validar el permiso
        y el alcance, y responde 403 o 404 si no corresponde.
      </p>
    </TarjetaUi>
  </div>
</template>
