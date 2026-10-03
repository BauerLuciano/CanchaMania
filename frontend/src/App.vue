<script setup>
/**
 * Raiz de la aplicacion.
 *
 * Decide el layout a partir del `meta.layout` de la ruta, que es la unica
 * fuente de esa decision: agregar una pantalla no obliga a tocar este archivo.
 * Tambien es donde se invoca el montaje unico.
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import { useMontaje } from './composables/useMontaje.js'
import PanelLayout from './layouts/PanelLayout.vue'
import PublicoLayout from './layouts/PublicoLayout.vue'

const route = useRoute()

useMontaje()

const layout = computed(() => (route.meta?.layout === 'publico' ? PublicoLayout : PanelLayout))
</script>

<template>
  <component :is="layout">
    <RouterView />
  </component>
</template>
