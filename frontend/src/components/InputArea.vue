<template>
  <div class="input-area">
    <div class="input-wrapper">
      <div class="composer-tools">
        <slot name="scenes" />
        <slot name="microphone" />
        <div class="capture-mode-row">
          <button type="button" @click="$emit('toggle-capture-mode')" class="capture-mode-toggle" title="点击切换截图发送方式">
            截图：{{ captureMode === 'collect' ? '累积' : '逐张' }}
          </button>
          <span v-if="captureConnected" class="capture-label" :title="captureSourceName">{{ captureSourceName || '已共享' }}</span>
          <button v-if="captureConnected" type="button" @click="$emit('reset-capture')">更换来源</button>
          <span v-if="pendingCaptureCount">待发 {{ pendingCaptureCount }}</span>
          <span v-if="activeCaptureCount">回答中 {{ activeCaptureCount }}</span>
          <button v-if="pendingCaptureCount" type="button" @click="$emit('clear-captures')">清空</button>
        </div>
      </div>
      <div v-if="pendingCaptures.length" class="pending-captures">
        <div v-for="item in pendingCaptures" :key="item.id" class="pending-capture">
          <img :src="item.url" alt="待发送截图" />
          <button type="button" :aria-label="'移除截图 ' + item.id" @click="$emit('remove-capture', item.id)">×</button>
        </div>
      </div>
      <div class="input-container" :class="{ focused: isFocused }">
        <div class="textarea-wrapper">
          <textarea 
            ref="textarea"
            :value="modelValue"
            @input="handleInput"
            @keydown="handleKeyDown"
            @compositionstart="handleCompositionStart"
            @compositionend="handleCompositionEnd"
            @focus="isFocused = true"
            @blur="isFocused = false"
            rows="1"
            placeholder="写下问题，开始对话…"
            aria-label="消息输入"
            class="input-textarea"
          ></textarea>
        </div>
        <span class="capture-anchor-space" aria-hidden="true"></span>
        <button 
          @click="$emit('send')"
          :disabled="captureResponsesActive || (!isSending && !modelValue.trim() && !pendingCaptureCount)"
          class="send-button"
          :class="{ 
            active: !isSending && (modelValue.trim() || pendingCaptureCount),
            stop: isSending
          }"
          :title="captureResponsesActive ? '截图正在并行回答' : (isSending ? '停止生成' : '发送消息')"
          :aria-label="captureResponsesActive ? '截图正在并行回答' : (isSending ? '停止生成' : '发送消息')"
        >
          <svg v-if="!isSending" class="send-icon" viewBox="0 0 20 20" aria-hidden="true">
            <path d="M10 15.5V4.5M5.75 8.75 10 4.5l4.25 4.25" />
          </svg>
          <span v-else class="stop-icon" aria-hidden="true"></span>
        </button>
      </div>
      <div class="composer-hint"><span>文字 · 语音 · 截图</span><span>Enter 发送 <span class="hint-divider">/</span> Shift + Enter 换行</span></div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted } from 'vue'

const props = defineProps({
  modelValue: {
    type: String,
    required: true
  },
  isSending: {
    type: Boolean,
    default: false
  },
  isRecording: { type: Boolean, default: false },
  captureConnected: {
    type: Boolean,
    default: false
  },
  captureSourceName: {
    type: String,
    default: ''
  },
  captureMode: { type: String, default: 'immediate' },
  pendingCaptureCount: { type: Number, default: 0 },
  pendingCaptures: { type: Array, default: () => [] },
  captureResponsesActive: { type: Boolean, default: false },
  activeCaptureCount: { type: Number, default: 0 }
})

const emit = defineEmits(['update:modelValue', 'send', 'reset-capture', 'toggle-capture-mode', 'clear-captures', 'remove-capture'])

const textarea = ref(null)
const isFocused = ref(false)
let isComposing = false
let compositionEndedAt = 0

function handleInput(e) {
  emit('update:modelValue', e.target.value)
  adjustHeight()
}

function handleCompositionStart() {
  isComposing = true
}

function handleCompositionEnd() {
  isComposing = false
  compositionEndedAt = Date.now()
}

function handleKeyDown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    // 中文等输入法使用 Enter 确认候选词时，只上屏，不发送消息。
    // keyCode 229 和短暂延迟用于兼容 compositionend 早于 keydown 的浏览器。
    const isConfirmingImeInput =
      isComposing ||
      e.isComposing ||
      e.keyCode === 229 ||
      Date.now() - compositionEndedAt < 50

    if (isConfirmingImeInput) {
      return
    }

    e.preventDefault()
    emit('send')
  }
}

function adjustHeight(followLatest = false) {
  nextTick(() => {
    if (textarea.value) {
      const previousScrollTop = textarea.value.scrollTop
      textarea.value.style.height = 'auto'
      textarea.value.style.height = Math.min(textarea.value.scrollHeight, 200) + 'px'
      textarea.value.scrollTop = followLatest ? textarea.value.scrollHeight : previousScrollTop
    }
  })
}

// 语音转写通过 modelValue 更新，不会触发 textarea 的 input 事件。
watch(() => props.modelValue, () => {
  adjustHeight(props.isRecording || !isFocused.value)
})

onMounted(() => adjustHeight(true))
</script>

<style scoped>
.composer-tools { display:flex; align-items:center; flex-wrap:wrap; gap:6px 12px; margin-bottom:6px; }
.capture-meta-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  column-gap: 16px;
  padding: 0 4px 5px;
  min-height: 25px;
}
.capture-mode-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  color: #64748b;
  font-size: 12px;
}
.capture-mode-row button {
  border: 0;
  background: transparent;
  color: #4f46e5;
  cursor: pointer;
  padding: 2px 0;
}
.capture-mode-toggle span { color: #94a3b8; margin-left: 3px; }
.pending-captures { display: flex; gap: 7px; overflow-x: auto; padding: 2px 5px 8px; }
.pending-capture { position: relative; flex: 0 0 54px; height: 54px; }
.pending-capture img { width: 100%; height: 100%; object-fit: cover; border-radius: 8px; border: 1px solid #cbd5e1; }
.pending-capture button { position: absolute; top: -3px; right: -3px; width: 19px; height: 19px; padding: 0; border: 0; border-radius: 50%; color: white; background: #334155; cursor: pointer; }
.input-area {
  background: #f7f9fc;
  padding: 12px 20px 14px;
  width: 100%;
  flex-shrink: 0;
}

.input-wrapper {
  max-width: 1280px;
  width: 100%;
  margin: 0 auto;
  padding: 0 20px;
}

.capture-status {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
  max-width: 60%;
  color: #475569;
  font-size: 12px;
}

.capture-dot {
  width: 7px;
  height: 7px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, .14);
}

.capture-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.capture-reset {
  border: 0;
  padding: 1px 4px;
  background: transparent;
  color: #2563eb;
  cursor: pointer;
  font-size: 12px;
}

.input-container {
  display: flex;
  gap: 10px;
  align-items: flex-end;
  width: 100%;
  padding: 6px 7px 6px 18px;
  border: 1px solid rgba(148, 163, 184, .25);
  border-radius: 20px;
  background: #ffffff;
  box-shadow: 0 5px 18px rgba(15, 23, 42, .055);
  transition: border-color .18s ease, box-shadow .18s ease;
}

.input-container.focused {
  border-color: rgba(99, 140, 206, .6);
  box-shadow: 0 6px 22px rgba(37, 99, 235, .10);
}

.textarea-wrapper {
  flex: 1;
  position: relative;
  min-width: 0;
}

.input-textarea {
  appearance: none;
  display: block;
  box-sizing: border-box;
  width: 100%;
  min-height: 38px;
  padding: 6px 0;
  border: 0;
  border-radius: 0;
  font-size: 16px;
  line-height: 1.65;
  resize: none;
  max-height: 200px;
  overflow-y: auto;
  transition: color .18s ease;
  background: white;
  color: #1f2937;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  box-shadow: none;
}

.input-textarea:focus {
  outline: none;
  box-shadow: none;
}

.input-textarea:focus-visible {
  outline: none;
}

.input-textarea::placeholder {
  color: #9ca3af;
}

.send-button {
  width: 38px;
  height: 38px;
  min-width: 38px;
  min-height: 38px;
  margin: 2px;
  border-radius: 50%;
  border: none;
  background: #f1f3f6;
  color: #a8b0bc;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: not-allowed;
  transition: transform .18s ease, background .18s ease, color .18s ease, box-shadow .18s ease;
  flex-shrink: 0;
  align-self: flex-end;
}

.capture-anchor-space {
  width: 38px;
  height: 38px;
  min-width: 38px;
  margin: 2px 0 2px 2px;
  flex: 0 0 38px;
}

.send-icon {
  width: 20px;
  height: 20px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.stop-icon {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  background: currentColor;
}

@media (max-width: 720px) {
  .input-area { padding: 10px 8px 12px; }
  .input-wrapper { padding: 0 4px; }
  .input-container { gap: 8px; padding-left: 14px; }
}

.send-button.active {
  background: #202938;
  color: white;
  cursor: pointer;
  box-shadow: 0 3px 8px rgba(15, 23, 42, .18);
}

.send-button.active:hover {
  transform: translateY(-1px);
  background: #111827;
  box-shadow: 0 5px 11px rgba(15, 23, 42, .22);
}

.send-button.active:active {
  transform: translateY(0);
}

.send-button:focus-visible {
  outline: 3px solid rgba(59, 130, 246, .2);
  outline-offset: 2px;
}

.send-button.stop {
  background: #dc2626;
  color: white;
  cursor: pointer;
  box-shadow: 0 3px 9px rgba(220, 38, 38, .24);
  animation: pulse 2s ease-in-out infinite;
}

.send-button.stop:hover {
  transform: translateY(-1px);
  box-shadow: 0 5px 12px rgba(220, 38, 38, .28);
  background: #b91c1c;
}

.send-button.stop:active {
  transform: translateY(0);
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.8;
  }
}
</style>
