<template>
  <Teleport v-if="hasAnswers" to="#answer-highlight-controls">
    <button v-if="dismissed" class="overlay-control" @click="dismissed = false">显示大字答案</button>
    <button v-else class="overlay-control" title="关闭答案图层（双击页面或 Esc）" aria-label="关闭答案图层" @click="dismissed = true">× 关闭答案</button>
  </Teleport>
  <Teleport to="body">
    <div v-if="hasAnswers && !dismissed" class="answer-overlay" aria-label="最终答案高亮">

        <div class="overlay-models" :style="{ gridTemplateColumns: `repeat(${models.length}, minmax(0, 1fr))` }" aria-live="polite">
          <section v-for="model in models" :key="model.key" class="model-column" :aria-label="model.label">
            <span v-if="models.length > 1" class="model-label">{{ model.label }}</span>
            <div class="model-answers" :style="{ gridTemplateRows: `repeat(${Math.max(1, model.answers.length)}, minmax(0, 1fr))` }">
              <div v-for="(answer, index) in model.answers" :key="index" class="answer-card" :style="{ fontSize: answerSize(answer.answer) }">
                <strong>{{ answer.answer }}</strong>
                <span v-if="answer.question" class="question-number">{{ answer.question }}</span>
              </div>
            </div>
          </section>
        </div>

    </div>
  </Teleport>
</template>
<script setup>
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import { answerHighlightModels } from '../utils/answerHighlight'
const props = defineProps({ messages: { type: Array, default: () => [] } })
const dismissed = ref(false)
const latest = computed(() => {
  for (let i = props.messages.length - 1; i >= 0; i--) {
    if (props.messages[i].role === 'user') return null
    if (props.messages[i].role === 'assistant') return props.messages[i]
  }
  return null
})
const models = computed(() => answerHighlightModels(latest.value))
const hasAnswers = computed(() => models.value.some(model => model.answers.length))
// A second model finishing must not reopen an overlay the user already closed.
watch(hasAnswers, visible => { if (!visible) dismissed.value = false })
const rows = computed(() => Math.max(1, ...models.value.map(model => model.answers.length)))
function answerSize(answer) {
  return `min(${55 / rows.value}vh, ${82 / Math.max(1, models.value.length) / Math.max(1, answer.length * 0.72)}vw)`
}
function onKeyDown(event) {
  if (event.key === 'Escape' && hasAnswers.value) dismissed.value = true
}
function onDoubleClick(event) {
  if (hasAnswers.value && !event.target.closest?.('.overlay-control')) dismissed.value = true
}
onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('dblclick', onDoubleClick, true)
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('dblclick', onDoubleClick, true)
})
</script>
<style scoped>
.answer-overlay { position: fixed; inset: 0; z-index: 3000; pointer-events: none; background: transparent; }
.overlay-models { position: absolute; inset: 9vh 3vw 5vh; display: grid; gap: 16px; }
.model-column { display: flex; flex-direction: column; align-items: stretch; min-width: 0; min-height: 0; }
.model-label { align-self: center; color: #1e4d9c; font: 600 16px/1.4 Arial, sans-serif; background: rgb(255 255 255 / 75%); border-radius: 6px; padding: 4px 10px; max-width: 100%; overflow-wrap: anywhere; text-align: center; }
.model-answers { flex: 1; min-height: 0; display: grid; }
.answer-card { min-height: 0; min-width: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; color: rgb(30 92 230 / 30%); font-family: Arial, Helvetica, sans-serif; font-style: normal; font-weight: 400; }
.answer-card strong { font-family: inherit; font-size: 1em; font-weight: 500; line-height: 1; text-align: center; white-space: nowrap; }
.question-number { font-size: 0.333333em; font-weight: 400; line-height: 1.1; max-width: 100%; overflow-wrap: anywhere; text-align: center; }
.overlay-control { position: static; pointer-events: auto; min-height: 32px; padding: 4px 10px; border: 1px solid #abc3ed; border-radius: 12px; background: rgb(255 255 255 / 94%); color: #194b9f; box-shadow: 0 3px 16px rgb(25 75 159 / 15%); cursor: pointer; font-size: 13px; }
.overlay-control:hover { background: #e7efff; }
.overlay-control:focus-visible { outline: 3px solid #2868e8; outline-offset: 3px; }
</style>
