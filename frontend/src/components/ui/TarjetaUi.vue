<script setup>
/** Contenedor de contenido con titulo opcional. */
defineProps({
  titulo: { type: String, default: '' },
  descripcion: { type: String, default: '' },
})
</script>

<template>
  <section class="rounded-xl border border-slate-200 bg-white shadow-sm">
    <header v-if="titulo" class="border-b border-slate-200 px-5 py-4">
      <h2 class="text-base font-semibold text-slate-900">{{ titulo }}</h2>
      <p v-if="descripcion" class="mt-1 text-sm text-slate-600">{{ descripcion }}</p>
    </header>
    <div class="p-5">
      <slot />
    </div>
  </section>
</template>
