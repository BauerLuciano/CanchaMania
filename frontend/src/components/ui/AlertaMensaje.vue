<script setup>
/**
 * Aviso de error o de estado.
 *
 * Muestra el `mensaje` que devuelve el backend (SPEC §19). El `codigo` se ve
 * solo en detalle: sirve para que quien desarrollo lea la consola sin ensuciar
 * la pantalla, y la persona usuaria nunca tiene que interpretarlo.
 */
import { computed } from 'vue'

const props = defineProps({
  codigo: { type: String, default: '' },
  mensaje: { type: String, required: true },
  tipo: { type: String, default: 'error', validator: (v) => ['error', 'aviso', 'info'].includes(v) },
  mostrarCodigo: { type: Boolean, default: false },
})

const estilos = {
  error: 'border-red-200 bg-red-50 text-red-800',
  aviso: 'border-amber-200 bg-amber-50 text-amber-800',
  info: 'border-sky-200 bg-sky-50 text-sky-800',
}

const clases = computed(() => estilos[props.tipo])
</script>

<template>
  <div
    class="flex items-start gap-2.5 rounded-lg border px-3.5 py-3 text-sm"
    :class="clases"
    :role="tipo === 'error' ? 'alert' : 'status'"
  >
    <span class="mt-0.5 shrink-0" aria-hidden="true">
      <svg v-if="tipo === 'error'" viewBox="0 0 20 20" fill="currentColor" class="size-4">
        <path
          fill-rule="evenodd"
          d="M18 10A8 8 0 1 1 2 10a8 8 0 0 1 16 0Zm-8-4a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0v-3.5A.75.75 0 0 1 10 6Zm0 8a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
          clip-rule="evenodd"
        />
      </svg>
      <svg v-else viewBox="0 0 20 20" fill="currentColor" class="size-4">
        <path
          fill-rule="evenodd"
          d="M18 10A8 8 0 1 1 2 10a8 8 0 0 1 16 0Zm-7 4a1 1 0 1 1-2 0 1 1 0 0 1 2 0Zm-1-8a1 1 0 0 1 2 0c0 1.333-.5 2-1 2.5-.5.5-.8.833-.8 1.5a1 1 0 1 1-2 0c0-1.5.8-2.167 1.5-2.833.3-.3.5-.5.5-1.167Z"
          clip-rule="evenodd"
        />
      </svg>
    </span>

    <div class="min-w-0 flex-1">
      <p>{{ mensaje }}</p>
      <p v-if="mostrarCodigo && codigo" class="mt-1 font-mono text-xs opacity-70">{{ codigo }}</p>
    </div>

    <slot />
  </div>
</template>
