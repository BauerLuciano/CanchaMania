<script setup>
/**
 * Pantalla inicial del panel.
 *
 * Muestra unicamente lo que el backend ya entrego en `/api/auth/me/`. No consulta
 * nada nuevo: todo sale del store de sesion, que es una copia del perfil.
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { useAuthStore } from '../../stores/auth.js'
import BotonUi from '../../components/ui/BotonUi.vue'
import InsigniaUi from '../../components/ui/InsigniaUi.vue'
import TarjetaUi from '../../components/ui/TarjetaUi.vue'

const auth = useAuthStore()
const router = useRouter()
const { perfil, roles, negocios, sucursales, permisos, nombreMostrado } = storeToRefs(auth)

const tonoDeRol = (rol) =>
  ({ DUENO: 'dueno', ENCARGADO: 'encargado', CAJERO: 'cajero' })[rol] ?? 'neutro'

const resumen = computed(() => [
  { etiqueta: 'Roles', valor: roles.value.length, detalle: roles.value.join(' · ') || '—' },
  {
    etiqueta: 'Negocios',
    valor: negocios.value.length,
    detalle: negocios.value.some((n) => n.todo_el_negocio) ? 'con alcance total' : 'con alcance acotado',
  },
  {
    etiqueta: 'Sucursales',
    valor: sucursales.value.length,
    detalle: sucursales.value.length ? 'con alcance propio' : 'sin alcance por sede',
  },
  { etiqueta: 'Permisos', valor: permisos.value.size, detalle: 'devueltos por el backend' },
])
</script>

<template>
  <div class="flex flex-col gap-6">
    <TarjetaUi>
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div class="min-w-0">
          <p class="text-sm text-slate-600">Sesion iniciada como</p>
          <p class="truncate text-lg font-semibold text-slate-900">{{ nombreMostrado }}</p>
          <p class="truncate text-sm text-slate-500">{{ perfil?.email }}</p>
        </div>
        <div class="flex items-center gap-2">
          <InsigniaUi v-for="rol in roles" :key="rol" :texto="rol" :tono="tonoDeRol(rol)" />
        </div>
      </div>
    </TarjetaUi>

    <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <TarjetaUi v-for="dato in resumen" :key="dato.etiqueta">
        <p class="text-sm text-slate-600">{{ dato.etiqueta }}</p>
        <p class="mt-1 text-3xl font-semibold tracking-tight text-slate-900">{{ dato.valor }}</p>
        <p class="mt-1 text-xs text-slate-500">{{ dato.detalle }}</p>
      </TarjetaUi>
    </div>

    <TarjetaUi
      titulo="Etapa 1"
      descripcion="Base del sistema: sesion, permisos y multi-tenancy."
    >
      <p class="text-sm text-slate-600">
        El esqueleto del panel esta listo: ingreso con sesion Django, CSRF en toda escritura,
        proteccion de rutas y navegacion filtrada por los permisos que devuelve el backend.
      </p>
      <p class="mt-3 text-sm text-slate-600">
        Las secciones de negocios, sucursales, usuarios y membresias todavia no tienen pantalla:
        aparecen bloqueadas en el menu segun los permisos que tenes, y se implementan en las
        etapas siguientes.
      </p>

      <div class="mt-5 flex flex-wrap gap-3">
        <BotonUi variante="secundario" @click="router.push({ name: 'acceso' })">
          Ver mi acceso
        </BotonUi>
        <BotonUi variante="fantasma" @click="router.push({ name: 'login' })">
          Ir al ingreso
        </BotonUi>
      </div>
    </TarjetaUi>
  </div>
</template>
