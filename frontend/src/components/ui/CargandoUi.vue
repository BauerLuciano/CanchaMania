<script setup>
/** Estado de carga. `texto` permite anunciar la espera a lectores de pantalla. */
defineProps({
  texto: { type: String, default: 'Cargando...' },
})
</script>

<template>
  <div class="flex items-center justify-center gap-3 py-10 text-sm text-slate-500" role="status">
    <span
      class="size-5 animate-spin rounded-full border-2 border-slate-300 border-t-cancha-600"
      aria-hidden="true"
    />
    <span>{{ texto }}</span>
  </div>
</template>
