<script setup>
/**
 * Campo de formulario: etiqueta, control, ayuda y error.
 *
 * El `id` se genera si no se pasa y se enlaza con `label for`, para que al
 * navegar con teclado el foco caiga en el control correcto y los lectores de
 * pantalla asocien bien la etiqueta.
 */
import { computed, useId } from 'vue'

const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  etiqueta: { type: String, required: true },
  type: { type: String, default: 'text' },
  placeholder: { type: String, default: '' },
  ayuda: { type: String, default: '' },
  error: { type: String, default: '' },
  requerido: { type: Boolean, default: false },
  deshabilitado: { type: Boolean, default: false },
  autocomplete: { type: String, default: undefined },
})

const emit = defineEmits(['update:modelValue'])

const idAutomatico = useId()
const id = computed(() => props.ayuda || props.error ? `campo-${idAutomatico}` : undefined)
const idAyuda = computed(() => (id.value ? `${id.value}-ayuda` : undefined))
const idError = computed(() => (id.value ? `${id.value}-error` : undefined))

/** Describe el error para lectores de pantalla sin sacar el foco del campo. */
const descritoPor = computed(() => [idAyuda.value, props.error ? idError.value : null].filter(Boolean))
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label class="text-sm font-medium text-slate-700" :for="id">
      {{ etiqueta }}
      <span v-if="requerido" class="text-red-600" aria-hidden="true">*</span>
    </label>

    <input
      :id="id"
      :type="type"
      :value="modelValue"
      :placeholder="placeholder"
      :required="requerido"
      :disabled="deshabilitado"
      :autocomplete="autocomplete"
      :aria-invalid="error ? 'true' : undefined"
      :aria-describedby="descritoPor.length ? descritosPor.join(' ') : undefined"
      class="w-full rounded-lg border px-3 py-2.5 text-sm text-slate-900 shadow-sm transition
        placeholder:text-slate-400 disabled:cursor-not-allowed disabled:bg-slate-100
        focus:border-cancha-600 focus:ring-2 focus:ring-cancha-600/20 focus:outline-none
        aria-[invalid=true]:border-red-500 aria-[invalid=true]:ring-red-500/20"
      :class="error ? 'border-red-400' : 'border-slate-300'"
      @input="emit('update:modelValue', $event.target.value)"
    >

    <p v-if="ayuda && !error" :id="idAyuda" class="text-xs text-slate-500">{{ ayuda }}</p>
    <p v-if="error" :id="idError" class="text-xs font-medium text-red-600" role="alert">
      {{ error }}
    </p>
  </div>
</template>
