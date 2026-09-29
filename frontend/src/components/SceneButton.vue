<template>
  <button ref="button" type="button" class="scene-button" :class="{ selected, floating: position }"
    :style="position ? { left: position.left + 'px', top: position.top + 'px' } : {}"
    :aria-pressed="selected" :aria-disabled="disabled" :title="`${scene.description || scene.name}（拖动调整位置，右键复位）`"
    @pointerdown="start" @pointermove="move" @pointerup="end" @pointercancel="cancel"
    @click="click" @contextmenu.prevent="reset">
    <strong>{{ scene.name }}</strong><small v-if="scene.description">{{ scene.description }}</small>
  </button>
</template>
<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
const props = defineProps({ scene: Object, selected: Boolean, disabled: Boolean })
const emit = defineEmits(['select'])
const button = ref(null)
const position = ref(null)
let gesture = null
let suppressClick = false
const key = () => `prompt-scene-position:${props.scene.id}`
function persist() { try { localStorage.setItem(key(), JSON.stringify(position.value)) } catch {} }
function clamp(left, top) {
  return { left: Math.max(0, Math.min(left, innerWidth - (button.value?.offsetWidth || 150))), top: Math.max(0, Math.min(top, innerHeight - (button.value?.offsetHeight || 50))) }
}
function start(e) {
  if (e.button !== 0) return
  const rect = button.value.getBoundingClientRect()
  gesture = { id: e.pointerId, x: e.clientX, y: e.clientY, left: rect.left, top: rect.top, moved: false, original: position.value }
  suppressClick = false
  button.value.setPointerCapture(e.pointerId)
}
function move(e) {
  if (!gesture || e.pointerId !== gesture.id) return
  const dx = e.clientX - gesture.x, dy = e.clientY - gesture.y
  if (!gesture.moved && Math.hypot(dx, dy) < 6) return
  gesture.moved = true
  position.value = clamp(gesture.left + dx, gesture.top + dy)
}
function end(e) {
  if (!gesture || e.pointerId !== gesture.id) return
  suppressClick = gesture.moved
  if (gesture.moved) persist()
  gesture = null
}
function cancel() { if (gesture) position.value = gesture.original; gesture = null; suppressClick = true }
function click() { if (suppressClick) { suppressClick = false; return }; if (!props.disabled) emit('select') }
function reset() { position.value = null; persist() }
function resize() { if (position.value) position.value = clamp(position.value.left, position.value.top) }
onMounted(() => {
  try { const saved = JSON.parse(localStorage.getItem(key())); if (Number.isFinite(saved?.left) && Number.isFinite(saved?.top)) position.value = clamp(saved.left, saved.top) } catch {}
  window.addEventListener('resize', resize)
  window.addEventListener('reset-scene-positions', reset)
})
onUnmounted(() => { window.removeEventListener('resize', resize); window.removeEventListener('reset-scene-positions', reset) })
</script>
<style scoped>
.scene-button { display:flex; flex-direction:column; align-items:flex-start; gap:1px; max-width:220px; padding:4px 9px; border:1px solid #d8dfe9; border-radius:12px; color:#475569; background:#fff; cursor:grab; touch-action:none; user-select:none; text-align:left; }
.scene-button small { font-size:11px; max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.scene-button.selected { background:#eef2ff; border-color:#818cf8; color:#4338ca; }
.scene-button.floating { position:fixed; z-index:1100; box-shadow:0 3px 12px #0f172a26; }
.scene-button[aria-disabled=true] { opacity:.6; }
.scene-button:focus-visible { outline:2px solid #6366f1; outline-offset:2px; }
</style>
