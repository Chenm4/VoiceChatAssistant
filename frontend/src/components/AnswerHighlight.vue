<template>
  <Teleport v-if="hasAnswers" to="#answer-highlight-controls">
    <button v-if="dismissed" class="overlay-control" @click="dismissed = false">显示大字答案</button>
    <button v-else class="overlay-control" title="关闭答案图层（连点三下或 Esc）" aria-label="关闭答案图层" @click="dismissed = true">× 关闭答案</button>
  </Teleport>
  <Teleport to="body">
    <div v-if="hasAnswers" v-show="!dismissed" class="answer-overlay" :class="{ 'code-overlay': activePage?.type === 'code', 'stale-answer': isStale }" aria-label="最终答案高亮">

        <button type="button" class="overlay-close" aria-label="关闭放大浮层" title="关闭浮层（连点三下或 Esc）" @click="dismissed = true">× 关闭</button>
        <div class="overlay-models" :style="{ gridTemplateColumns: `repeat(${models.length}, minmax(0, 1fr))` }" aria-live="polite">
          <section v-for="(model, slot) in models" :key="slot" class="model-column" :aria-label="model.label">
            <span v-if="models.length > 1" class="model-label">{{ model.label }}</span>
            <CodeHighlightPane v-if="model.code" :key="activePage.messageIndex + ':' + activePage.question + ':' + slot" :code="model.code" :active="!dismissed" />
            <div v-else-if="model.answers.length" class="model-answers" :style="{ gridTemplateRows: `repeat(${Math.max(1, model.answers.length)}, minmax(0, 1fr))` }">
              <div v-for="(answer, index) in model.answers" :key="index" class="answer-card" :style="{ fontSize: answerSize(answer.answer) }">
                <strong>{{ answer.answer }}</strong>
                <span v-if="answer.question" class="question-number">{{ answer.question }}</span>
              </div>
            </div>
            <span v-else class="missing-answer">本题暂无答案</span>
          </section>
        </div>
        <nav class="answer-navigation" aria-label="切换高亮答案" @wheel.prevent="onWheel" @dblclick.stop>
          <button type="button" class="navigation-button" :disabled="activeIndex <= 0" @click="navigate(-1)">↑ 上一题</button>
          <span class="navigation-status" aria-live="polite">
            <span v-if="isStale" class="stale-label">旧答案</span>
            <strong>{{ activePage?.question ? `题号 ${activePage.question}` : '未标注题号' }}</strong>
            <span>{{ activeIndex + 1 }} / {{ pages.length }}</span>
          </span>
          <button type="button" class="navigation-button" :disabled="activeIndex >= pages.length - 1" @click="navigate(1)">下一题 ↓</button>
        </nav>
    </div>
  </Teleport>
</template>
<script setup>
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import { answerHighlightPages } from '../utils/answerHighlight'
import CodeHighlightPane from './CodeHighlightPane.vue'
const props = defineProps({ messages: { type: Array, default: () => [] } })
const emit = defineEmits(['navigate'])
const dismissed = ref(false)
const selectedKey = ref(null)
const followingLatest = ref(true)
const pages = computed(() => answerHighlightPages(props.messages))
const activeIndex = computed(() => pages.value.findIndex(page => page.key === selectedKey.value))
const activePage = computed(() => pages.value[activeIndex.value])
const models = computed(() => activePage.value?.models || [])
const hasAnswers = computed(() => pages.value.length > 0)
// Sending a question invalidates the displayed answer immediately, even before
// the next assistant message has any content (including parallel captures).
const isStale = computed(() => !!activePage.value && props.messages.some((message, index) =>
  message.role === 'user' && index > activePage.value.messageIndex))
watch(pages, (items, previous = []) => {
  if (!items.length) {
    selectedKey.value = null
    dismissed.value = false
    followingLatest.value = true
    return
  }
  const newest = items.at(-1).messageIndex
  let currentExists = items.some(page => page.key === selectedKey.value)
  // A server refresh assigns IDs to optimistic messages. Keep the same question
  // selected instead of resetting to the first page when only its ID changes.
  if (!currentExists) {
    const previousPage = previous.find(page => page.key === selectedKey.value)
    const replacement = previousPage && items.find(page =>
      page.messageIndex === previousPage.messageIndex &&
      JSON.parse(page.key)[1] === JSON.parse(previousPage.key)[1])
    if (replacement) {
      selectedKey.value = replacement.key
      currentExists = true
    }
  }
  const newMessage = newest !== previous.at(-1)?.messageIndex
  if (!currentExists || (followingLatest.value && newMessage)) {
    selectedKey.value = items.find(page => page.messageIndex === newest).key
    if (newMessage) dismissed.value = false
  }
}, { immediate: true })
function navigate(direction) {
  const next = activeIndex.value + direction
  if (next < 0 || next >= pages.value.length) return
  followingLatest.value = false
  selectedKey.value = pages.value[next].key
  emit('navigate', pages.value[next].messageIndex)
}
let lastWheel = 0
let wheelDelta = 0
function onWheel(event) {
  const now = Date.now()
  if (now - lastWheel < 250) return
  if (Math.sign(event.deltaY) !== Math.sign(wheelDelta)) wheelDelta = 0
  wheelDelta += event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? window.innerHeight : 1)
  if (Math.abs(wheelDelta) < 35) return
  navigate(Math.sign(wheelDelta))
  wheelDelta = 0
  lastWheel = now
}
function answerSize(answer) {
  return `min(48vh, ${82 / Math.max(1, models.value.length) / Math.max(1, answer.length * 0.72)}vw)`
}
function onKeyDown(event) {
  if (event.key === 'Escape' && hasAnswers.value) dismissed.value = true
}
let pointerStart = null
let dragged = false
function onPointerDown(event) {
  pointerStart = { x: event.clientX, y: event.clientY }
  dragged = false
}
function onPointerMove(event) {
  if (pointerStart && Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y) > 6) dragged = true
}
function onClick(event) {
  if (!hasAnswers.value || dismissed.value || dragged || event.button !== 0 || event.detail !== 3) return
  if (event.target.closest?.('button, a, input, textarea, select, [contenteditable="true"], .answer-navigation')) return
  dismissed.value = true
}
onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('pointerdown', onPointerDown, true)
  window.addEventListener('pointermove', onPointerMove, true)
  window.addEventListener('click', onClick, true)
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('pointerdown', onPointerDown, true)
  window.removeEventListener('pointermove', onPointerMove, true)
  window.removeEventListener('click', onClick, true)
})
</script>
<style scoped>
.answer-overlay { position: fixed; inset: 0; z-index: 3000; pointer-events: none; background: transparent; }
.overlay-models { position: absolute; inset: 9vh 3vw max(110px, 18vh); display: grid; gap: 16px; }
.model-column { display: flex; flex-direction: column; align-items: stretch; min-width: 0; min-height: 0; }
.model-label { align-self: center; color: #1e4d9c; font: 600 16px/1.4 Arial, sans-serif; background: rgb(255 255 255 / 75%); border-radius: 6px; padding: 4px 10px; max-width: 100%; overflow-wrap: anywhere; text-align: center; }
.model-answers { flex: 1; min-height: 0; display: grid; }
.answer-card { min-height: 0; min-width: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; color: rgb(30 92 230 / 30%); font-family: Arial, Helvetica, sans-serif; font-style: normal; font-weight: 400; }
.stale-answer .answer-card { color: rgb(100 110 125 / 35%); }
.stale-answer .model-label { color: #626c7a; background: rgb(240 242 245 / 85%); }
.stale-answer :deep(.code-highlight-pane) { color: #626c7a; border-color: #b8bec7; background: rgb(240 242 245 / 88%); }
.stale-label { color: #59616d; background: #edf0f3; border: 1px solid #cbd0d8; border-radius: 4px; padding: 1px 6px; font-size: 12px; font-weight: 600; }
.answer-card strong { font-family: inherit; font-size: 1em; font-weight: 500; line-height: 1; text-align: center; white-space: nowrap; }
.question-number { font-size: 0.333333em; font-weight: 400; line-height: 1.1; max-width: 100%; overflow-wrap: anywhere; text-align: center; }
.missing-answer { margin: auto; color: #536787; padding: 12px; background: rgb(255 255 255 / 85%); border-radius: 10px; }
.answer-navigation { position: absolute; bottom: max(20px, env(safe-area-inset-bottom)); left: 50%; transform: translateX(-50%); display: flex; align-items: center; justify-content: center; gap: 16px; width: max-content; max-width: calc(100vw - 24px); padding: 12px; border: 1px solid #abc3ed; border-radius: 18px; background: rgb(255 255 255 / 96%); box-shadow: 0 6px 24px rgb(25 75 159 / 18%); pointer-events: auto; }
.navigation-button { min-height: 56px; min-width: 132px; padding: 12px 20px; border: 1px solid #2868e8; border-radius: 12px; background: #e7efff; color: #194b9f; font-size: 18px; font-weight: 600; cursor: pointer; touch-action: manipulation; }
.navigation-button:hover:not(:disabled) { background: #d6e5ff; }
.navigation-button:disabled { opacity: 0.4; cursor: default; }
.navigation-button:focus-visible { outline: 3px solid #2868e8; outline-offset: 3px; }
.navigation-status { display: flex; flex-direction: column; align-items: center; gap: 4px; color: #194b9f; min-width: 70px; max-width: 180px; overflow-wrap: anywhere; text-align: center; font-size: 14px; }
@media (max-width: 480px) {
  .answer-navigation { gap: 8px; padding: 8px; }
  .navigation-button { min-width: 90px; padding: 10px; font-size: 16px; }
  .navigation-status { min-width: 52px; max-width: 100px; }
}
.overlay-control { position: static; pointer-events: auto; min-height: 32px; padding: 4px 10px; border: 1px solid #abc3ed; border-radius: 12px; background: rgb(255 255 255 / 94%); color: #194b9f; box-shadow: 0 3px 16px rgb(25 75 159 / 15%); cursor: pointer; font-size: 13px; }
.overlay-control:hover { background: #e7efff; }
.overlay-control:focus-visible { outline: 3px solid #2868e8; outline-offset: 3px; }
.overlay-close { position: absolute; top: max(12px, env(safe-area-inset-top)); right: 12px; z-index: 2; pointer-events: auto; min-height: 44px; padding: 8px 20px; border: 1px solid #c45b65; border-radius: 12px; background: #fff; color: #a52435; font-size: 18px; font-weight: 600; cursor: pointer; box-shadow: 0 3px 16px #0002; }
.overlay-close:hover { background: #fff0f1; }
.overlay-close:focus-visible { outline: 3px solid #2868e8; outline-offset: 2px; }
.code-overlay .overlay-models { inset: max(78px, calc(env(safe-area-inset-top) + 66px)) 12px max(8px, env(safe-area-inset-bottom)); gap: 12px; }
.code-overlay .answer-navigation { top: max(8px, env(safe-area-inset-top)); bottom: auto; padding: 6px 10px; gap: 10px; }
.code-overlay .navigation-button { min-height: 44px; padding: 6px 12px; min-width: 100px; font-size: 16px; }
@media (max-width: 600px) {
  .code-overlay .answer-navigation { left: 8px; transform: none; max-width: calc(100vw - 100px); gap: 4px; padding: 6px; }
  .code-overlay .navigation-button { min-width: 64px; padding: 6px; font-size: 13px; }
  .code-overlay .navigation-status { min-width: 40px; max-width: 70px; font-size: 12px; }
  .overlay-close { right: 8px; padding: 8px 10px; font-size: 16px; }
}
</style>
