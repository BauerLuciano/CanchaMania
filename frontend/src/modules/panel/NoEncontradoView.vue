<script setup>
/** Ruta inexistente. Distinta si hay sesion o no, porque el destino cambia. */
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { useAuthStore } from '../../stores/auth.js'
import BotonUi from '../../components/ui/BotonUi.vue'
import TarjetaUi from '../../components/ui/TarjetaUi.vue'

const auth = useAuthStore()
const router = useRouter()
const { autenticado } = storeToRefs(auth)
</script>

<template>
  <div class="flex min-h-[60vh] items-center justify-center">
    <TarjetaUi class="max-w-md">
      <p class="text-sm font-semibold text-cancha-700">Error 404</p>
      <h1 class="mt-1 text-lg font-semibold text-slate-900">Esta pagina no existe</h1>
      <p class="mt-2 text-sm text-slate-600">
        El enlace puede estar mal escrito o haber cambiado. Volve al panel para seguir trabajando.
      </p>

      <div class="mt-6">
        <BotonUi @click="router.push({ name: autenticado ? 'panel' : 'login' })">
          {{ autenticado ? 'Volver al panel' : 'Ir al ingreso' }}
        </BotonUi>
      </div>
    </TarjetaUi>
  </div>
</template>
