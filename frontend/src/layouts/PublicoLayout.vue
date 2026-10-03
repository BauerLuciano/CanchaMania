<script setup>
/**
 * Layout publico: centrado y sin navegacion.
 *
 * Lo usan las pantallas que no dependen del panel (el login). El fondo es el
 * mismo que el panel para que el cambio de layout no se note como un salto.
 */
defineProps({
  titulo: { type: String, default: '' },
  descripcion: { type: String, default: '' },
})
</script>

<template>
  <div class="flex min-h-screen flex-col items-center justify-center px-4 py-10">
    <main class="w-full max-w-md">
      <header class="mb-8 text-center">
        <RouterLink to="/" class="inline-flex items-center gap-2">
          <span
            class="flex size-10 items-center justify-center rounded-xl bg-cancha-700 text-lg font-bold text-white"
            aria-hidden="true"
          >
            CM
          </span>
          <span class="text-2xl font-semibold tracking-tight text-slate-900">CanchaMania</span>
        </RouterLink>
        <p v-if="descripcion" class="mt-3 text-sm text-slate-600">{{ descripcion }}</p>
      </header>

      <slot />
    </main>
  </div>
</template>
