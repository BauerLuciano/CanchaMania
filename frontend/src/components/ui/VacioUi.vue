<script setup>
/** Estado vacio: no es un error, es que todavia no hay nada para mostrar. */
defineProps({
  titulo: { type: String, default: 'Todavia no hay nada aqui' },
  descripcion: { type: String, default: '' },
})
</script>

<template>
  <div class="rounded-lg border border-dashed border-slate-300 px-6 py-10 text-center">
    <p class="text-sm font-medium text-slate-700">{{ titulo }}</p>
    <p v-if="descripcion" class="mx-auto mt-1 max-w-md text-sm text-slate-500">{{ descripcion }}</p>
    <div class="mt-4">
      <slot />
    </div>
  </div>
</template>
