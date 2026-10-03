<script setup>
/** Insignia para roles y estados. */
defineProps({
  texto: { type: String, required: true },
  tono: { type: String, default: 'neutro' },
})

const tonos = {
  neutro: 'bg-slate-100 text-slate-700 ring-slate-200',
  dueno: 'bg-cancha-100 text-cancha-800 ring-cancha-200',
  encargado: 'bg-sky-100 text-sky-800 ring-sky-200',
  cajero: 'bg-amber-100 text-amber-800 ring-amber-200',
  aviso: 'bg-amber-100 text-amber-800 ring-amber-200',
}
</script>

<template>
  <span
    class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset"
    :class="tonos[tono] ?? tonos.neutro"
  >
    {{ texto }}
  </span>
</template>
