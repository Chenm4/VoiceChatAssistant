<template>
  <div class="reasoning-buttons" role="group" :aria-label="label">
    <button v-for="option in options" :key="option.value" type="button"
      :aria-pressed="value === option.value" :class="{ selected: value === option.value }"
      :disabled="disabled" :title="value === option.value ? '当前思考强度' : `以${option.label}思考强度重新回答`"
      @click="choose(option.value)">{{ option.label }}</button>
  </div>
</template>
<script setup>
const props = defineProps({ options: Array, value: String, label: String, disabled: Boolean })
const emit = defineEmits(['change'])
function choose(value) {
  if (!props.disabled && value !== props.value) emit('change', value)
}
</script>
<style scoped>
.reasoning-buttons { display: flex; gap: 4px; max-width: 100%; overflow-x: auto; padding: 3px; border: 1px solid #e5e7eb; border-radius: 8px; background: #f7f7f8; }
.reasoning-buttons button { flex: 0 0 auto; border: 1px solid transparent; border-radius: 5px; padding: 3px 7px; background: transparent; color: #737373; font-size: 12px; line-height: 1.5; cursor: pointer; white-space: nowrap; }
.reasoning-buttons button:hover:not(:disabled) { background: #e9edf3; color: #334155; }
.reasoning-buttons button.selected { background: white; border-color: #cbd5e1; color: #2563eb; font-weight: 600; }
.reasoning-buttons button:disabled { opacity: .55; cursor: not-allowed; }
.reasoning-buttons button:focus-visible { outline: 2px solid #93c5fd; outline-offset: -1px; }
</style>
