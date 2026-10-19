<template>
  <button
    ref="button"
    type="button"
    class="capture-float-button"
    :class="{ connected, loading, ready }"
    :style="{ width: `${size}px`, height: `${size}px` }"
    :aria-disabled="disabled"
    :title="(connected ? '左键拍照，拖动调整位置' : '左键连接所选来源并拍照，拖动调整位置') + (rightClickAction === 'photo' ? '；右键拍照' : '；右键语音识别／停止')"
    aria-label="截图答题"
    @pointerdown="handlePointerDown"
    @keydown.enter.prevent="!disabled && $emit('capture')"
    @keydown.space.prevent="!disabled && $emit('capture')"
  >
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 7.5h3l1.4-2h7.2l1.4 2h3v11H4z" />
      <circle cx="12" cy="13" r="3.2" />
    </svg>
    <span v-if="connected" class="connected-dot"></span>
  </button>
</template>

<script setup>
import { userStorage } from '../utils/auth'

import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps({
  rightClickAction: { type: String, default: 'record' },
  size: { type: Number, default: 64 },
  connected: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false }
})

const emit = defineEmits(['capture', 'cancel'])
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
  const width = button.value?.offsetWidth || props.size
  const height = button.value?.offsetHeight || props.size
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
  applyPosition(rect.left, rect.top + (rect.height - (button.value?.offsetHeight || props.size)) / 2)
}

function loadPosition() {
  try {
    const stored = JSON.parse(userStorage.getItem(STORAGE_KEY) || 'null')
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
  userStorage.setItem(STORAGE_KEY, JSON.stringify({
    left: currentLeft,
    top: currentTop
  }))
}

function resetPosition() {
  userStorage.removeItem(STORAGE_KEY)
  customPosition = false
  positionAtDefaultAnchor()
}

function handlePointerDown(event) {
  if (props.disabled) return
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
  } else if (!props.disabled) {
    emit('capture')
  }
  pointerId = null
}

function handleResize() {
  if (customPosition) applyPosition(currentLeft, currentTop)
  else positionAtDefaultAnchor()
}

defineExpose({ reposition: handleResize })

watch(() => props.size, () => nextTick(handleResize))

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
  width: 64px;
  height: 64px;
  border: 0;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  color: #4f46e5;
  box-shadow: none;
  cursor: grab;
  touch-action: none;
  user-select: none;
  opacity: 0;
  transition: transform .16s ease, background .16s ease, color .16s ease, opacity .16s ease;
}

.capture-float-button.ready { opacity: 1; }

.capture-float-button:hover:not(:disabled) {
  transform: translateY(-1px) scale(1.04);
  background: transparent;
}

.capture-float-button:active:not(:disabled) { cursor: grabbing; }
.capture-float-button.ready:disabled { cursor: not-allowed; opacity: .55; }
.capture-float-button.connected { background: transparent; color: #059669; }
.capture-float-button.loading svg { animation: capture-spin .9s linear infinite; }

.capture-float-button svg {
  width: 68%;
  height: 68%;
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
