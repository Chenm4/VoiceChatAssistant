<template>
  <button
    ref="button"
    type="button"
    class="capture-float-button"
    :class="{ connected, loading, ready }"
    :disabled="disabled"
    :title="connected ? '截图并直接发送（可拖动，右键复位）' : '选择窗口或标签页并截图（可拖动，右键复位）'"
    aria-label="截图答题"
    @pointerdown="handlePointerDown"
    @contextmenu.prevent="resetPosition"
    @keydown.enter.prevent="$emit('capture')"
    @keydown.space.prevent="$emit('capture')"
  >
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 7.5h3l1.4-2h7.2l1.4 2h3v11H4z" />
      <circle cx="12" cy="13" r="3.2" />
    </svg>
    <span v-if="connected" class="connected-dot"></span>
  </button>
</template>

<script setup>
import { nextTick, onMounted, onUnmounted, ref } from 'vue'

defineProps({
  connected: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false }
})

const emit = defineEmits(['capture'])
const button = ref(null)
const ready = ref(false)
const STORAGE_KEY = 'captureButtonPosition'
const DRAG_THRESHOLD = 5

let dragging = false
let moved = false
let pointerId = null
let startX = 0
let startY = 0
let startLeft = 0
let startTop = 0
let currentLeft = 0
let currentTop = 0
let customPosition = false
let animationFrameId = null
let layoutObserver = null

function clampPosition(left, top) {
  const width = button.value?.offsetWidth || 38
  const height = button.value?.offsetHeight || 38
  return {
    left: Math.max(8, Math.min(left, window.innerWidth - width - 8)),
    top: Math.max(8, Math.min(top, window.innerHeight - height - 8))
  }
}

function applyPosition(left, top) {
  if (!button.value) return
  const position = clampPosition(left, top)
  currentLeft = position.left
  currentTop = position.top
  button.value.style.left = `${position.left}px`
  button.value.style.top = `${position.top}px`
  ready.value = true
}

function positionAtDefaultAnchor() {
  const anchor = document.querySelector('.capture-anchor-space')
  if (!anchor) return
  const rect = anchor.getBoundingClientRect()
  applyPosition(rect.left, rect.top + (rect.height - (button.value?.offsetHeight || 38)) / 2)
}

function loadPosition() {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null')
    if (Number.isFinite(stored?.left) && Number.isFinite(stored?.top)) {
      customPosition = true
      applyPosition(stored.left, stored.top)
      return
    }
  } catch (error) {
    console.warn('读取截图按钮位置失败:', error)
  }
  customPosition = false
  positionAtDefaultAnchor()
}

function savePosition() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({
    left: currentLeft,
    top: currentTop
  }))
}

function resetPosition() {
  localStorage.removeItem(STORAGE_KEY)
  customPosition = false
  positionAtDefaultAnchor()
}

function handlePointerDown(event) {
  if (event.button !== undefined && event.button !== 0) return
  event.preventDefault()
  pointerId = event.pointerId
  button.value?.setPointerCapture?.(pointerId)
  const rect = button.value.getBoundingClientRect()
  startX = event.clientX
  startY = event.clientY
  startLeft = rect.left
  startTop = rect.top
  currentLeft = startLeft
  currentTop = startTop
  dragging = true
  moved = false
  window.addEventListener('pointermove', handlePointerMove, { passive: false })
  window.addEventListener('pointerup', handlePointerUp)
  window.addEventListener('pointercancel', handlePointerUp)
}

function handlePointerMove(event) {
  if (!dragging || event.pointerId !== pointerId) return
  event.preventDefault()
  const deltaX = event.clientX - startX
  const deltaY = event.clientY - startY
  if (!moved && Math.hypot(deltaX, deltaY) < DRAG_THRESHOLD) return
  moved = true
  currentLeft = startLeft + deltaX
  currentTop = startTop + deltaY
  if (!animationFrameId) {
    animationFrameId = requestAnimationFrame(() => {
      applyPosition(currentLeft, currentTop)
      animationFrameId = null
    })
  }
}

function handlePointerUp(event) {
  if (!dragging || event.pointerId !== pointerId) return
  dragging = false
  button.value?.releasePointerCapture?.(pointerId)
  window.removeEventListener('pointermove', handlePointerMove)
  window.removeEventListener('pointerup', handlePointerUp)
  window.removeEventListener('pointercancel', handlePointerUp)
  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId)
    animationFrameId = null
    applyPosition(currentLeft, currentTop)
  }
  if (moved) {
    customPosition = true
    savePosition()
  } else {
    emit('capture')
  }
  pointerId = null
}

function handleResize() {
  if (customPosition) applyPosition(currentLeft, currentTop)
  else positionAtDefaultAnchor()
}

onMounted(() => {
  nextTick(() => {
    loadPosition()
    layoutObserver = new ResizeObserver(() => {
      if (!customPosition && !dragging) positionAtDefaultAnchor()
    })
    for (const selector of ['.chat-view', '.input-container', '.input-area']) {
      const element = document.querySelector(selector)
      if (element) layoutObserver.observe(element)
    }
  })
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  layoutObserver?.disconnect()
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('pointermove', handlePointerMove)
  window.removeEventListener('pointerup', handlePointerUp)
  window.removeEventListener('pointercancel', handlePointerUp)
  if (animationFrameId) cancelAnimationFrame(animationFrameId)
})
</script>

<style scoped>
.capture-float-button {
  position: fixed;
  left: 0;
  top: 0;
  z-index: 1100;
  width: 38px;
  height: 38px;
  border: 0;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #eef2ff;
  color: #4f46e5;
  box-shadow: 0 3px 10px rgba(15, 23, 42, .16);
  cursor: grab;
  touch-action: none;
  user-select: none;
  opacity: 0;
  transition: transform .16s ease, background .16s ease, color .16s ease, opacity .16s ease;
}

.capture-float-button.ready { opacity: 1; }

.capture-float-button:hover:not(:disabled) {
  transform: translateY(-1px) scale(1.04);
  background: #e0e7ff;
}

.capture-float-button:active:not(:disabled) { cursor: grabbing; }
.capture-float-button.ready:disabled { cursor: not-allowed; opacity: .55; }
.capture-float-button.connected { background: #ecfdf5; color: #059669; }
.capture-float-button.loading svg { animation: capture-spin .9s linear infinite; }

.capture-float-button svg {
  width: 20px;
  height: 20px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
  pointer-events: none;
}

.connected-dot {
  position: absolute;
  right: 1px;
  top: 1px;
  width: 8px;
  height: 8px;
  border: 2px solid white;
  border-radius: 50%;
  background: #22c55e;
}

@keyframes capture-spin { to { transform: rotate(360deg); } }
</style>
