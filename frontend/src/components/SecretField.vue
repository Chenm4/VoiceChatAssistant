<template>
  <div class="secret-field">
    <input :type="visible ? 'text' : 'password'" :value="modelValue" :aria-label="label"
      autocomplete="off" spellcheck="false" @input="$emit('update:modelValue', $event.target.value)">
    <button type="button" :aria-label="(visible ? '隐藏' : '查看') + label" :aria-pressed="visible" @click="visible = !visible">
      {{ visible ? '隐藏' : '查看' }}
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
defineProps({ modelValue: { type: String, default: '' }, label: { type: String, default: 'API Key' } })
defineEmits(['update:modelValue'])
const visible = ref(false)
</script>

<style scoped>
.secret-field { display: flex; gap: 8px; }
.secret-field input { flex: 1; min-width: 0; padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 8px; }
.secret-field button { padding: 6px 10px; color: #2563eb; border: 1px solid #cbd5e1; border-radius: 8px; }
</style>
