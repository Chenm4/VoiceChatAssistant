<template>
  <details class="answer-versions">
    <summary>查看旧回答（{{ versions.length }} 个版本）</summary>
    <select v-model="selected" aria-label="选择旧回答版本">
      <option v-for="(version, index) in versions" :key="index" :value="index">{{ index + 1 }} · {{ version.scene_name || '会话原配置' }}</option>
    </select>
    <div v-for="(answer, index) in answers" :key="index" class="old-answer">
      <small>{{ answer.model_info?.name || answer.model || '' }}</small>
      <div class="markdown-body" v-html="renderMarkdown(answer.content || '')"></div>
    </div>
  </details>
</template>
<script setup>
import { computed, ref } from 'vue'
import { renderMarkdown } from '../utils/markdown'
const props = defineProps({ versions: { type: Array, required: true } })
const selected = ref(0)
const answers = computed(() => { const version = props.versions[selected.value] || props.versions[0]; return version?.parallel_models || (version ? [version] : []) })
</script>
<style scoped>
.answer-versions { margin:8px 0; padding:8px 12px; border:1px solid #e2e8f0; border-radius:10px; color:#64748b; font-size:13px; }
summary { cursor:pointer; } select { margin:10px 0; max-width:100%; } .old-answer { color:#334155; overflow:auto; }
</style>
