<template>
  <div class="input-area">
    <div class="input-wrapper">
      <div v-if="captureConnected" class="capture-status">
        <span class="capture-dot"></span>
        <span class="capture-label" :title="captureSourceName">正在捕获：{{ captureSourceName || '已选择标签页' }}</span>
        <button class="capture-reset" type="button" @click="$emit('reset-capture')">更换标签页</button>
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
            placeholder="输入问题，Enter 发送，Shift + Enter 换行"
            class="input-textarea"
          ></textarea>
        </div>
        <span class="capture-anchor-space" aria-hidden="true"></span>
        <button 
          @click="$emit('send')"
          :disabled="!isSending && !modelValue.trim()"
          class="send-button"
          :class="{ 
            active: !isSending && modelValue.trim(),
            stop: isSending
          }"
          :title="isSending ? '停止生成' : '发送消息'"
          :aria-label="isSending ? '停止生成' : '发送消息'"
        >
          <svg v-if="!isSending" class="send-icon" viewBox="0 0 20 20" aria-hidden="true">
            <path d="M10 15.5V4.5M5.75 8.75 10 4.5l4.25 4.25" />
          </svg>
          <span v-else class="stop-icon" aria-hidden="true"></span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  modelValue: {
    type: String,
    required: true
  },
  isSending: {
    type: Boolean,
    default: false
  },
  captureConnected: {
    type: Boolean,
    default: false
  },
  captureSourceName: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue', 'send', 'reset-capture'])

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

function adjustHeight() {
  nextTick(() => {
    if (textarea.value) {
      textarea.value.style.height = 'auto'
      textarea.value.style.height = Math.min(textarea.value.scrollHeight, 200) + 'px'
    }
  })
}

// 监听值变化，调整高度
watch(() => props.modelValue, () => {
  if (props.modelValue === '') {
    nextTick(() => {
      if (textarea.value) {
        textarea.value.style.height = 'auto'
      }
    })
  }
})
</script>

<style scoped>
.input-area {
  border-bottom: 1px solid #e8edf4;
  background: #ffffff;
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
  min-height: 24px;
  padding: 0 10px 6px;
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
  border: 1px solid #d9e0ea;
  border-radius: 18px;
  background: #ffffff;
  box-shadow: 0 2px 8px rgba(15, 23, 42, .045);
  transition: border-color .18s ease, box-shadow .18s ease;
}

.input-container.focused {
  border-color: #8bb8ff;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, .10), 0 4px 14px rgba(15, 23, 42, .055);
}

.textarea-wrapper {
  flex: 1;
  position: relative;
  min-width: 0;
}

.input-textarea {
  display: block;
  box-sizing: border-box;
  width: 100%;
  min-height: 42px;
  padding: 8px 0 7px;
  border: 0;
  border-radius: 0;
  font-size: 16px;
  line-height: 1.65;
  resize: none;
  max-height: 200px;
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
