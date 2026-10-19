<template>
  <details v-if="text" class="reasoning-content" :open="expanded" @toggle="expanded = $event.target.open">
    <summary>{{ streaming && !hasAnswer ? '正在思考…' : '思考过程' }}</summary>
    <div class="reasoning-text">{{ text }}</div>
  </details>
  <div v-else-if="streaming && !hasAnswer" class="reasoning-wait" role="status">正在等待模型输出…</div>
</template>
<script setup>
import { ref, watch } from 'vue'
const props = defineProps({ text: String, streaming: Boolean, hasAnswer: Boolean })
const expanded = ref(Boolean(props.streaming && !props.hasAnswer))
watch(() => props.streaming && !props.hasAnswer, shouldOpen => {
  if (shouldOpen) expanded.value = true
})
</script>
<style scoped>
.reasoning-content { margin-bottom: 14px; border-left: 2px solid #d1d5db; padding: 4px 12px; color: #64748b; font-size: 13px; }
.reasoning-content summary { cursor: pointer; }
.reasoning-text { white-space: pre-wrap; overflow-wrap: anywhere; max-height: 260px; overflow-y: auto; line-height: 1.65; margin-top: 8px; }
.reasoning-wait { color: #64748b; font-size: 13px; padding: 8px 0; }
</style>
