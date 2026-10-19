<template>
  <button 
    ref="button"
    :aria-label="buttonLabel"
    :title="buttonLabel + (rightClickAction === 'photo' ? '（右键拍照）' : '（左键默认混音识别，右键声卡单路；同来源再次点击停止）')"
    :aria-busy="phase !== 'idle'"
    @mousedown="handleMouseDown"
    @touchstart="handleTouchStart"
    @keydown.enter.prevent="phase === 'idle' && $emit('toggle')"
    @keydown.space.prevent="phase === 'idle' && $emit('toggle')"
    class="voice-button flex items-center justify-center text-white"
    :class="{ recording: isRecording, processing: phase !== 'idle' }"
  >
    <span class="source-badge">{{ modeLabel }}</span>
    <div class="button-content">
      <span v-if="['starting', 'stopping', 'switching'].includes(phase)" class="microphone-progress" aria-hidden="true"></span>
      <svg class="microphone-meter" viewBox="0 0 24 28" aria-hidden="true">
        <defs>
          <clipPath :id="meterClipId">
            <rect x="8" y="2" width="8" height="16" rx="4" />
          </clipPath>
        </defs>
        <rect class="mic-capsule" x="8" y="2" width="8" height="16" rx="4" />
        <g :clip-path="`url(#${meterClipId})`">
          <rect class="mic-level" x="8" width="8" :y="18 - audioVolume * 16" :height="audioVolume * 16" />
        </g>
        <rect class="mic-outline" x="8" y="2" width="8" height="16" rx="4" />
        <path class="mic-stand" d="M5 12v4a7 7 0 0 0 14 0v-4M12 23v3M8 26h8" />
      </svg>
    </div>
    <!-- <div class="tooltip">{{ isRecording ? '停止录音' : '点击录音' }}</div> -->
  </button>
</template>

<script setup>
import { ref, computed, getCurrentInstance, onUnmounted } from 'vue'

const props = defineProps({
  rightClickAction: { type: String, default: 'record' },
  isRecording: {
    type: Boolean,
    default: false
  },
  audioLevel: { type: Number, default: 0 },
  phase: { type: String, default: 'idle' },
  inputSource: { type: String, default: 'microphone' },
  modeLabel: { type: String, default: '双路混音' }
})

const emit = defineEmits(['toggle'])
const buttonLabel = computed(() => props.phase === 'starting' ? '正在启动语音识别' : props.phase === 'stopping' ? '正在提交识别结果' : props.phase === 'switching' ? '正在切换输入设备' : props.phase === 'cancelling' ? '正在取消识别' : props.isRecording ? (props.inputSource === 'usb' ? '切换为混音识别' : '停止' + props.modeLabel + '识别') : '开始' + props.modeLabel + '识别')

const button = ref(null)
const meterClipId = `microphone-level-${getCurrentInstance().uid}`
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
  if (e.button !== 0 || props.phase !== 'idle') return
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
  if (props.phase !== 'idle') return
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
.source-badge { position: absolute; bottom: 2px; left: 50%; transform: translateX(-50%); padding: 2px 5px; border-radius: 5px; background: #ffffffe6; color: #555; font-size: 10px; line-height: 1.2; white-space: nowrap; pointer-events: none; }
.voice-button { position: fixed; right: 30px; bottom: 30px; width: 64px; height: 64px; border-radius: 50%; cursor: move; z-index: 1000; user-select: none; border: 2px solid #d1d5db; background: transparent; overflow: visible; touch-action: none; }
.voice-button:focus-visible { outline: 3px solid #86efac; outline-offset: 3px; }
.microphone-progress { position: absolute; inset: -10px; border: 2px solid transparent; border-top-color: #73777e; border-radius: 50%; animation: mic-progress .8s linear infinite; }
@keyframes mic-progress { to { transform: rotate(360deg); } }
.button-content { position: relative; width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; }
.microphone-meter { width: 28px; height: 32px; overflow: visible; }
.mic-capsule { fill: #edf0f2; }
.mic-level { fill: #20c66b; transition: y .1s linear, height .1s linear; }
.mic-outline, .mic-stand { fill: none; stroke: #72777d; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
.recording .mic-outline, .recording .mic-stand { stroke: #43494f; }
@media (prefers-reduced-motion: reduce) { .microphone-progress { animation: none; border-style: dotted; border-color: #73777e; } .mic-level { transition: none; } }
</style>
