/**
 * Montaje unico de la aplicacion (SPEC §21: "Montos mediante un unico
 * composable").
 *
 * `App.vue` lo llama una sola vez. Acá se cablea lo que es global y no
 * pertenece a ninguna pantalla:
 *
 * 1. Recuperar la sesion al arrancar.
 * 2. Reaccionar a un 401 de cualquier peticion: descartar el estado local y
 *    llevar al login. Es lo que hace que una sesion caducada a mitad de uso no
 *    deje al usuario en una pantalla muerta.
 */
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

import { alCaerLaSesion } from '../api/client.js'
import { useAuthStore } from '../stores/auth.js'

/**
 * @param {object} opciones
 * @param {boolean} opciones.montar  Falso para probar sin instalar los
 *                                   escuchadores (por ejemplo, en tests).
 */
export function useMontaje({ montar = true } = {}) {
  const auth = useAuthStore()
  const router = useRouter()

  let quitarOyente = null

  onMounted(async () => {
    if (montar) {
      quitarOyente = alCaerLaSesion(() => {
        // La API ya dijo que no hay sesion: se limpia el estado y se corta la
        // navegacion actual para que no queden datos viejos en pantalla.
        auth.olvidarLocal()
        if (router.currentRoute.value.meta?.requiereAuth) {
          router.push({
            name: 'login',
            query: { next: router.currentRoute.value.fullPath },
          })
        }
      })
    }

    await auth.restaurar()
  })

  onUnmounted(() => {
    if (quitarOyente) {
      quitarOyente()
      quitarOyente = null
    }
  })
}
