<script setup>
/**
 * Ingreso al panel.
 *
 * El formulario delega en `authApi` via el store: aca no hay `fetch` ni reglas
 * de negocio, solo Recoleccion de datos y presentacion del error que devuelve el
 * backend.
 *
 * Sobre CSRF: el backend lo exige tambien en el login. `client.js` lo pide solo
 * (`GET /api/auth/csrf/`) antes de la primera escritura, asi que esta pantalla
 * no tiene que saber nada del token. Si el servidor lo rechaza con
 * `CSRF_INVALIDO`, el cliente descarta el token y el proximo intento pasa con uno
 * nuevo: por eso el error no se trata como definitiva.
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { useAuthStore } from '../../stores/auth.js'
import { pedirTokenCsrf } from '../../api/authApi.js'
import AlertaMensaje from '../../components/ui/AlertaMensaje.vue'
import BotonUi from '../../components/ui/BotonUi.vue'
import CampoUi from '../../components/ui/CampoUi.vue'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const { ocupado } = storeToRefs(auth)

const formulario = reactive({ email: '', contrasena: '' })
const error = ref(null)
const csrfListo = ref(false)

/** Destino posterior al ingreso, validado para no seguir enlaces ajenos. */
const destino = computed(() => {
  const next = route.query.next
  // Solo se admiten rutas internas que empiezan con una barra y no con "//",
  // que seria un protocolo-relativo (posible redireccion fuera del sitio).
  return typeof next === 'string' && next.startsWith('/') && !next.startsWith('//')
    ? next
    : '/panel'
})

onMounted(async () => {
  // Se pide el token al montar, para que la primera escritura ya lo tenga.
  // Si falla, el propio `client.js` lo reintenta antes de enviar el formulario.
  try {
    await pedirTokenCsrf()
    csrfListo.value = true
  } catch {
    csrfListo.value = false
  }
})

async function ingresar() {
  error.value = null
  try {
    await auth.ingresar({ ...formulario })
    formulario.contrasena = ''
    router.replace(destino.value)
  } catch (excepcion) {
    // El backend es el que decide el motivo: credenciales invalidas, sin
    // membresias activas (`SIN_AMBITO`), CSRF, validacion o red. Se muestra su
    // mensaje sin reinterpretarlo.
    error.value = excepcion
    if (excepcion.csrfInvalido) {
      try {
        await pedirTokenCsrf(true)
      } catch {
        csrfListo.value = false
      }
    }
  }
}
</script>

<template>
  <div class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
    <header class="mb-6">
      <h1 class="text-xl font-semibold tracking-tight text-slate-900">Iniciar sesion</h1>
      <p class="mt-1 text-sm text-slate-600">
        Ingresa con el email con el que te dieron de alta.
      </p>
    </header>

    <AlertaMensaje
      v-if="error"
      class="mb-5"
      :mensaje="error.mensaje"
      :codigo="error.codigo"
    />

    <form class="flex flex-col gap-4" novalidate @submit.prevent="ingresar">
      <CampoUi
        v-model="formulario.email"
        etiqueta="Email"
        type="email"
        placeholder="nombre@negocio.com"
        autocomplete="email"
        requerido
      />

      <CampoUi
        v-model="formulario.contrasena"
        etiqueta="Contrasena"
        type="password"
        autocomplete="current-password"
        requerido
      />

      <BotonUi tipo="submit" ancho-completo :cargando="ocupado">
        {{ ocupado ? 'Entrando...' : 'Entrar' }}
      </BotonUi>
    </form>

    <AlertaMensaje
      v-if="!csrfListo"
      class="mt-4"
      tipo="aviso"
      mensaje="No se pudo preparar la proteccion CSRF todavia. Si el ingreso falla, recargá la página e intentá de nuevo."
    />

    <p class="mt-6 text-center text-xs text-slate-500">
      Si no podes entrar, consulta con el Dueño del negocio: el alta de usuarios
      se hace desde el panel, no desde esta pantalla.
    </p>
  </div>
</template>
