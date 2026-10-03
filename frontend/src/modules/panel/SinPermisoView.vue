<script setup>
/**
 * Aviso de falta de permiso.
 *
 * Apunta a la ruta pedida con `query.de`. No intenta adivinar si el recurso
 * existe: la guarda sabe que la ruta existe, no que el backend tenga los datos.
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { useAuthStore } from '../../stores/auth.js'
import BotonUi from '../../components/ui/BotonUi.vue'
import TarjetaUi from '../../components/ui/TarjetaUi.vue'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const { roles, esSuperadmin } = storeToRefs(auth)

const destino = computed(() => (typeof route.query.de === 'string' ? route.query.de : null))

async function cerrarSesion() {
  await auth.cerrar()
  router.push({ name: 'login' })
}
</script>

<template>
  <TarjetaUi titulo="No tenes permiso para esta seccion">
    <p class="text-sm text-slate-600">
      Tu rol no incluye el permiso que necesita esta pantalla. El backend no devolvio ese permiso
      en tu perfil, asi que el panel no la muestra.
    </p>

    <dl class="mt-5 grid gap-4 sm:grid-cols-2">
      <div>
        <dt class="text-sm text-slate-500">Roles actuales</dt>
        <dd class="mt-1 font-medium text-slate-900">{{ roles.join(' · ') || '—' }}</dd>
      </div>
      <div v-if="destino">
        <dt class="text-sm text-slate-500">Seccion pedida</dt>
        <dd class="mt-1 font-mono text-sm text-slate-900">{{ destino }}</dd>
      </div>
    </dl>

    <p v-if="esSuperadmin" class="mt-4 text-sm text-slate-600">
      Tenes superadmin, asi que el backend te devuelve todos los permisos. Si esto aparece, es un
      problema del frontend.
    </p>
    <p v-else class="mt-4 text-sm text-slate-600">
      Si necesitas esta seccion, pedile a un Dueño del negocio que ajuste tu membresia.
    </p>

    <div class="mt-6 flex flex-wrap gap-3">
      <BotonUi variante="secundario" @click="router.push({ name: 'panel' })">Volver al panel</BotonUi>
      <BotonUi variante="fantasma" @click="router.push({ name: 'acceso' })">Ver mi acceso</BotonUi>
      <BotonUi variante="fantasma" @click="cerrarSesion">Cambiar de usuario</BotonUi>
    </div>
  </TarjetaUi>
</template>
