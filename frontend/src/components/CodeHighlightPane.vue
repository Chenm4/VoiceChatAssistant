<template>
  <div class="code-highlight-pane" @dblclick.stop>
    <div class="code-tools">
      <span>{{ code.language }} · {{ Math.round(scale * 100) }}%</span>
      <span>滚轮缩放 · 左键拖动 · ↑↓移动</span>
      <button type="button" @click="scale = 1.5">重置</button>
    </div>
    <div ref="viewport" class="code-canvas" tabindex="0" aria-label="放大代码，滚轮缩放，左键拖动，上下键滚动"
      :class="{ dragging: drag }" @wheel.prevent.stop="zoom" @pointerdown="startDrag"
      @pointermove="moveDrag" @pointerup="endDrag" @pointercancel="endDrag" @lostpointercapture="drag = null">
      <pre :style="{ fontSize: `${20 * scale}px` }"><code>{{ code.code }}</code></pre>
    </div>
  </div>
</template>
<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
const props = defineProps({ code: { type: Object, required: true }, active: { type: Boolean, default: true } })
const scale = ref(1.5)
const viewport = ref(null)
const drag = ref(null)
function zoom(event) {
  const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? 400 : 1)
  scale.value = Math.max(.5, Math.min(4, scale.value * Math.exp(-Math.max(-100, Math.min(100, delta)) * .002)))
}
function startDrag(event) {
  if (event.button !== 0) return
  const element = viewport.value
  element.focus({ preventScroll: true })
  element.setPointerCapture(event.pointerId)
  drag.value = { id: event.pointerId, x: event.clientX, y: event.clientY, left: element.scrollLeft, top: element.scrollTop }
  event.preventDefault()
}
function moveDrag(event) {
  if (!drag.value || event.pointerId !== drag.value.id) return
  viewport.value.scrollLeft = drag.value.left - (event.clientX - drag.value.x)
  viewport.value.scrollTop = drag.value.top - (event.clientY - drag.value.y)
}
function endDrag(event) {
  if (!drag.value || event.pointerId !== drag.value.id) return
  drag.value = null
  if (viewport.value.hasPointerCapture(event.pointerId)) viewport.value.releasePointerCapture(event.pointerId)
}
function keydown(event) {
  if (!props.active) return
  if (!['ArrowUp', 'ArrowDown'].includes(event.key) || event.ctrlKey || event.metaKey || event.altKey) return
  if (event.target?.closest?.('input, textarea, select, [contenteditable="true"], [role="dialog"]')) return
  event.preventDefault()
  viewport.value?.scrollBy({ top: event.key === 'ArrowDown' ? 64 : -64, behavior: 'auto' })
}
onMounted(() => window.addEventListener('keydown', keydown))
onUnmounted(() => window.removeEventListener('keydown', keydown))
</script>
<style scoped>
.code-highlight-pane { display: flex; flex-direction: column; flex: 1; min-height: 0; min-width: 0; margin-top: 8px; pointer-events: auto; background: rgb(246 249 255 / 88%); border: 1px solid #adc4eb; border-radius: 12px; overflow: hidden; box-shadow: 0 6px 24px #194b9f18; color: #244e94; }
.code-tools { display: flex; gap: 10px; align-items: center; justify-content: space-between; flex-wrap: wrap; padding: 8px 12px; font: 13px/1.4 sans-serif; }
.code-tools button { background: white; border: 1px solid #adc4eb; border-radius: 6px; padding: 5px 10px; color: inherit; cursor: pointer; }
.code-canvas { flex: 1; min-height: 0; overflow: auto; overscroll-behavior: contain; cursor: grab; touch-action: none; user-select: none; }
.code-canvas.dragging { cursor: grabbing; }
.code-canvas:focus-visible { outline: 2px solid #2868e8; outline-offset: -2px; }
pre { margin: 0; padding: 20px; min-width: max-content; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; line-height: 1.5; white-space: pre; tab-size: 4; }
code { font: inherit; }
</style>
