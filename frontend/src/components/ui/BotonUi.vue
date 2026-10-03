<script setup>
/**
 * Boton del sistema visual.
 *
 * Un unico componente para todos los botones evita que cada pantalla invente sus
 * propios colores y estados de foco o de carga.
 */
import { computed } from 'vue'

const props = defineProps({
  variante: {
    type: String,
    default: 'primario',
    validator: (v) => ['primario', 'secundario', 'peligro', 'fantasma'].includes(v),
  },
  tamano: { type: String, default: 'md', validator: (v) => ['sm', 'md'].includes(v) },
  tipo: { type: String, default: 'button' },
  cargando: { type: Boolean, default: false },
  deshabilitado: { type: Boolean, default: false },
  anchoCompleto: { type: Boolean, default: false },
})

const emit = defineEmits(['click'])

const clasesBase =
  'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition ' +
  'disabled:cursor-not-allowed disabled:opacity-60'

const variantes = {
  primario: 'bg-cancha-700 text-white hover:bg-cancha-800 active:bg-cancha-900',
  secundario: 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50',
  peligro: 'bg-red-600 text-white hover:bg-red-700',
  fantasma: 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
}

const tamanos = { sm: 'px-2.5 py-1.5 text-sm', md: 'px-4 py-2.5 text-sm' }

const clases = computed(() =>
  [clasesBase, variantes[props.variante], tamanos[props.tamano], props.anchoCompleto ? 'w-full' : '']
    .filter(Boolean)
    .join(' '),
)

/** Un boton ocupado no debe disparar su accion. */
function alClic(evento) {
  if (props.cargando || props.deshabilitado) {
    evento.preventDefault()
    return
  }
  emit('click', evento)
}
</script>

<template>
  <button :type="tipo" :class="clases" :disabled="cargando || deshabilitado" @click="alClic">
    <span
      v-if="cargando"
      class="size-4 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent"
      aria-hidden="true"
    />
    <slot />
  </button>
</template>
