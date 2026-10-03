/**
 * Bootstrap de CanchaMania.
 *
 * Este archivo solo instala la aplicacion: estilos, Pinia y router. No decide
 * nada de sesion ni de rutas; eso vive en `composables/useMontaje.js`, que
 * `App.vue` invoca una sola vez.
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import { crearRouter } from './router/index.js'
import './assets/main.css'

const app = createApp(App)
const pinia = createPinia()
const router = crearRouter(pinia)

app.use(pinia)
app.use(router)

app.mount('#app')
