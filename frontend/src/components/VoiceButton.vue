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
  >
    <div class="button-content">
      <AppIcon :name="isRecording ? 'stop' : 'microphone'" class=" text-2xl icon"  />
      <!-- 录音时显示音频波纹 - 根据音量动态变化 -->
      <div v-if="isRecording" class="audio-rings" :style="{ '--volume': audioVolume }">
        <div class="pulse-ring ring-1"></div>
        <div class="pulse-ring ring-2"></div>
        <div class="pulse-ring ring-3"></div>
      </div>
    </div>
    <!-- <div class="tooltip">{{ isRecording ? '停止录音' : '点击录音' }}</div> -->
  </button>
</template>

<script setup>
import { ref, watch, onUnmounted } from 'vue'

const props = defineProps({
  isRecording: {
    type: Boolean,
    default: false
  },
  audioStream: {
    type: MediaStream,
    default: null
  }
})

const emit = defineEmits(['toggle'])

const button = ref(null)
const audioVolume = ref(0)

// 拖动相关
let isDragging = false
let startX = 0
let startY = 0
let startLeft = 0
let startTop = 0
let currentX = 0
let currentY = 0
let animationFrameId = null

// 音频分析相关
let audioContext = null
let analyser = null
let dataArray = null
let volumeAnimationId = null

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

// 初始化音频分析
function initAudioAnalysis() {
  if (!props.audioStream) return
  
  try {
    audioContext = new (window.AudioContext || window.webkitAudioContext)()
    const source = audioContext.createMediaStreamSource(props.audioStream)
    
    analyser = audioContext.createAnalyser()
    analyser.fftSize = 256
    analyser.smoothingTimeConstant = 0.8
    
    dataArray = new Uint8Array(analyser.frequencyBinCount)
    source.connect(analyser)
    
    // 开始分析音量
    analyzeVolume()
  } catch (error) {
    console.warn('无法初始化音频分析:', error)
  }
}

// 分析音量并更新波纹强度
function analyzeVolume() {
  if (!analyser || !props.isRecording) {
    audioVolume.value = 0
    return
  }
  
  volumeAnimationId = requestAnimationFrame(analyzeVolume)
  
  analyser.getByteFrequencyData(dataArray)
  
  // 计算平均音量
  let sum = 0
  for (let i = 0; i < dataArray.length; i++) {
    sum += dataArray[i]
  }
  const average = sum / dataArray.length
  
  // 归一化到 0-1 范围，并增强灵敏度
  const normalizedVolume = Math.min(average / 128, 1)
  
  // 平滑过渡
  audioVolume.value = audioVolume.value * 0.7 + normalizedVolume * 0.3
}

// 停止音频分析
function stopAudioAnalysis() {
  if (volumeAnimationId) {
    cancelAnimationFrame(volumeAnimationId)
    volumeAnimationId = null
  }
  
  if (audioContext) {
    audioContext.close()
    audioContext = null
  }
  
  analyser = null
  dataArray = null
  audioVolume.value = 0
}

// 监听录音状态和音频流
watch(() => [props.isRecording, props.audioStream], ([recording, stream]) => {
  if (recording && stream) {
    setTimeout(() => {
      initAudioAnalysis()
    }, 100)
  } else {
    stopAudioAnalysis()
  }
}, { immediate: true })

// 组件卸载时清理
onUnmounted(() => {
  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId)
  }
  stopAudioAnalysis()
})
</script>

<style scoped>
.voice-button {
  position: fixed;
  right: 30px;
  bottom: 30px;
  width: 64px;
  height: 64px;
  border-radius: 50%;
  cursor: move;
  z-index: 1000;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  transition: transform 0.2s ease, box-shadow 0.2s ease, background 0.3s ease, border-color 0.3s ease;
  user-select: none;
  border: 2px solid rgba(156, 163, 175, 0.3);
  background: transparent;
  backdrop-filter: none;
  overflow: visible;
  touch-action: none;
  will-change: transform;
}

.voice-button:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  border-color: rgba(156, 163, 175, 0.5);
  background: rgba(156, 163, 175, 0.08);
}

.voice-button:active {
  transform: scale(0.95);
}

.voice-button.recording {
  /* 根据音量动态变化背景色和边框 */
  background: linear-gradient(
    135deg, 
    rgba(239, 68, 68, calc(0.3 + var(--volume, 0) * 0.7)) 0%, 
    rgba(220, 38, 38, calc(0.3 + var(--volume, 0) * 0.7)) 100%
  );
  border-color: rgba(239, 68, 68, calc(0.5 + var(--volume, 0) * 0.5));
  /* 阴影也根据音量变化 */
  box-shadow: 0 calc(4px + var(--volume, 0) * 12px) calc(12px + var(--volume, 0) * 24px) rgba(239, 68, 68, calc(0.3 + var(--volume, 0) * 0.4));
  transition: background 0.1s ease, border-color 0.1s ease, box-shadow 0.1s ease;
}

.voice-button.recording:hover {
  box-shadow: 0 calc(6px + var(--volume, 0) * 14px) calc(16px + var(--volume, 0) * 28px) rgba(239, 68, 68, calc(0.4 + var(--volume, 0) * 0.5));
}

.button-content {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon {
  position: relative;
  z-index: 2;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.1));
  color: #6b7280;
  transition: color 0.3s ease;
}

.voice-button.recording .icon {
  /* 图标颜色也根据音量变化，音量小时偏灰，音量大时纯白 */
  color: rgb(
    calc(255 - (255 - 239) * (1 - var(--volume, 0))),
    calc(255 - (255 - 68) * (1 - var(--volume, 0))),
    calc(255 - (255 - 68) * (1 - var(--volume, 0)))
  );
  transition: color 0.1s ease;
}

.audio-rings {
  position: absolute;
  width: 100%;
  height: 100%;
  top: 0;
  left: 0;
  pointer-events: none;
}

.pulse-ring {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  /* 波纹颜色根据音量变化，从淡红到亮红 */
  border: 2px solid rgba(
    239, 
    68, 
    68, 
    calc(0.4 + var(--volume, 0) * 0.6)
  );
  top: 0;
  left: 0;
  /* 动画速度根据音量变化，音量大时波纹更快 */
  animation: volumePulse calc(1.8s / max(var(--volume, 0.2), 0.5)) ease-out infinite;
  opacity: calc(0.2 + var(--volume, 0) * 0.8);
}

.ring-1 {
  animation-delay: 0s;
}

.ring-2 {
  animation-delay: 0.6s;
}

.ring-3 {
  animation-delay: 1.2s;
}

.tooltip {
  position: absolute;
  bottom: 75px;
  left: 50%;
  transform: translateX(-50%) scale(0);
  background: rgba(31, 41, 55, 0.95);
  color: white;
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 13px;
  white-space: nowrap;
  pointer-events: none;
  transition: transform 0.2s ease;
  backdrop-filter: blur(10px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.tooltip::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border: 6px solid transparent;
  border-top-color: rgba(31, 41, 55, 0.95);
}

.voice-button:hover .tooltip {
  transform: translateX(-50%) scale(1);
}

@keyframes pulse {
  0% {
    transform: scale(1);
    opacity: 1;
  }
  100% {
    transform: scale(1.8);
    opacity: 0;
  }
}

@keyframes volumePulse {
  0% {
    transform: scale(1);
    opacity: calc(0.7 * (0.2 + var(--volume, 0) * 0.8));
  }
  100% {
    /* 扩散范围根据音量变化，音量大时扩散更远 */
    transform: scale(calc(1.5 + var(--volume, 0) * 1.0));
    opacity: 0;
  }
}

/* 移除固定的脉冲动画，改用音量驱动的动态效果 */
</style>
