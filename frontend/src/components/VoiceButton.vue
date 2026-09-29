<template>
  <button 
    ref="button"
    :aria-label="isRecording ? '停止录音' : '开始语音输入'"
    :title="isRecording ? '停止录音' : '开始语音输入（可拖动）'"
    @mousedown="handleMouseDown"
    @touchstart="handleTouchStart"
    @keydown.enter.prevent="$emit('toggle')"
    @keydown.space.prevent="$emit('toggle')"
    class="voice-button flex items-center justify-center text-white"
    :class="isRecording ? 'recording' : ''"
    :style="{ '--volume': audioVolume }"
  >
    <div class="button-content">
      <div v-if="isRecording" class="volume-glow" aria-hidden="true"></div>
      <AppIcon name="microphone" class="text-2xl icon" />
    </div>
    <!-- <div class="tooltip">{{ isRecording ? '停止录音' : '点击录音' }}</div> -->
  </button>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'

const props = defineProps({
  isRecording: {
    type: Boolean,
    default: false
  },
  audioLevel: { type: Number, default: 0 }
})

const emit = defineEmits(['toggle'])

const button = ref(null)
const audioVolume = computed(() => props.isRecording ? Math.max(0, Math.min(1, Number(props.audioLevel) || 0)) : 0)

// 拖动相关
let isDragging = false
let startX = 0
let startY = 0
let startLeft = 0
let startTop = 0
let currentX = 0
let currentY = 0
let animationFrameId = null

// 优化的拖动处理
function handleMouseDown(e) {
  e.preventDefault()
  isDragging = false
  startX = e.clientX
  startY = e.clientY
  
  const rect = button.value.getBoundingClientRect()
  startLeft = rect.left
  startTop = rect.top
  currentX = startLeft
  currentY = startTop
  
  document.addEventListener('mousemove', onMouseMove, { passive: false })
  document.addEventListener('mouseup', onMouseUp)
}

function handleTouchStart(e) {
  const touch = e.touches[0]
  isDragging = false
  startX = touch.clientX
  startY = touch.clientY
  
  const rect = button.value.getBoundingClientRect()
  startLeft = rect.left
  startTop = rect.top
  currentX = startLeft
  currentY = startTop
  
  document.addEventListener('touchmove', onTouchMove, { passive: false })
  document.addEventListener('touchend', onTouchEnd)
}

function onMouseMove(e) {
  e.preventDefault()
  const deltaX = e.clientX - startX
  const deltaY = e.clientY - startY
  
  if (Math.abs(deltaX) > 5 || Math.abs(deltaY) > 5) {
    isDragging = true
    currentX = startLeft + deltaX
    currentY = startTop + deltaY
    
    // 使用 RAF 优化性能
    if (!animationFrameId) {
      animationFrameId = requestAnimationFrame(updatePosition)
    }
  }
}

function onTouchMove(e) {
  e.preventDefault()
  const touch = e.touches[0]
  const deltaX = touch.clientX - startX
  const deltaY = touch.clientY - startY
  
  if (Math.abs(deltaX) > 5 || Math.abs(deltaY) > 5) {
    isDragging = true
    currentX = startLeft + deltaX
    currentY = startTop + deltaY
    
    if (!animationFrameId) {
      animationFrameId = requestAnimationFrame(updatePosition)
    }
  }
}

function updatePosition() {
  if (button.value && isDragging) {
    // 边界检测
    const maxX = window.innerWidth - button.value.offsetWidth
    const maxY = window.innerHeight - button.value.offsetHeight
    
    currentX = Math.max(0, Math.min(currentX, maxX))
    currentY = Math.max(0, Math.min(currentY, maxY))
    
    button.value.style.left = currentX + 'px'
    button.value.style.top = currentY + 'px'
    button.value.style.right = 'auto'
    button.value.style.bottom = 'auto'
  }
  animationFrameId = null
}

function onMouseUp() {
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseup', onMouseUp)
  
  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId)
    animationFrameId = null
  }
  
  if (!isDragging) {
    emit('toggle')
  }
  
  setTimeout(() => {
    isDragging = false
  }, 100)
}

function onTouchEnd() {
  document.removeEventListener('touchmove', onTouchMove)
  document.removeEventListener('touchend', onTouchEnd)
  
  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId)
    animationFrameId = null
  }
  
  if (!isDragging) {
    emit('toggle')
  }
  
  setTimeout(() => {
    isDragging = false
  }, 100)
}

onUnmounted(() => {
  if (animationFrameId) cancelAnimationFrame(animationFrameId)
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseup', onMouseUp)
  document.removeEventListener('touchmove', onTouchMove)
  document.removeEventListener('touchend', onTouchEnd)
})
</script>

<style scoped>
.voice-button { position: fixed; right: 30px; bottom: 30px; width: 64px; height: 64px; border-radius: 50%; cursor: move; z-index: 1000; user-select: none; border: 2px solid #d1d5db; background: white; overflow: visible; touch-action: none; }
.voice-button:focus-visible { outline: 3px solid #86efac; outline-offset: 3px; }
.button-content { position: relative; width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; }
.icon { position: relative; z-index: 2; color: #6b7280; transition: transform .12s ease, color .12s ease; }
.recording .icon { transform: scale(calc(1 + var(--volume) * .18)); }
.volume-glow { position: absolute; width: 42px; height: 42px; border-radius: 50%; background: #22c55e; opacity: calc(var(--volume) * .8); transform: scale(calc(.45 + var(--volume) * .8)); box-shadow: 0 0 calc(var(--volume) * 12px) #22c55e80; transition: transform .12s ease-out, opacity .12s ease-out; pointer-events: none; }
@media (prefers-reduced-motion: reduce) { .volume-glow, .icon { transition: none; transform: none !important; } }
</style>
