<template>
  <div class="input-area">
    <div class="input-wrapper">
      <div class="input-container">
        <div class="textarea-wrapper">
          <textarea 
            ref="textarea"
            :value="modelValue"
            @input="handleInput"
            @keydown="handleKeyDown"
            @focus="isFocused = true"
            @blur="isFocused = false"
            rows="1"
            placeholder=""
            class="input-textarea"
            :class="{ focused: isFocused }"
          ></textarea>
        </div>
        <button 
          @click="$emit('send')"
          :disabled="!isSending && !modelValue.trim()"
          class="send-button"
          :class="{ 
            active: !isSending && modelValue.trim(),
            stop: isSending
          }"
          :title="isSending ? '停止生成' : '发送消息'"
        >
          <i v-if="!isSending" class="fas fa-paper-plane"></i>
          <i v-else class="fas fa-stop"></i>
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
  }
})

const emit = defineEmits(['update:modelValue', 'send'])

const textarea = ref(null)
const isFocused = ref(false)

function handleInput(e) {
  emit('update:modelValue', e.target.value)
  adjustHeight()
}

function handleKeyDown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
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
  border-top: 1px solid #e5e7eb;
  background: linear-gradient(to top, #ffffff 0%, #fafafa 100%);
  padding: 20px 16px;
  backdrop-filter: blur(10px);
  width: 100%;
  flex-shrink: 0;
}

.input-wrapper {
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
  padding: 0 24px;
}

.input-container {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  width: 100%;
}

.textarea-wrapper {
  flex: 1;
  position: relative;
}

.input-textarea {
  width: 100%;
  padding: 14px 18px;
  border: 2px solid #e5e7eb;
  border-radius: 16px;
  font-size: 15px;
  line-height: 1.6;
  resize: none;
  max-height: 200px;
  transition: all 0.3s ease;
  background: white;
  color: #1f2937;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.input-textarea:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.input-textarea.focused {
  background: #ffffff;
}

.input-textarea::placeholder {
  color: #9ca3af;
}

.send-button {
  width: 48px;
  height: 48px;
  min-width: 48px;
  min-height: 48px;
  border-radius: 12px;
  border: none;
  background: #e5e7eb;
  color: #9ca3af;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: not-allowed;
  transition: all 0.3s ease;
  font-size: 18px;
  flex-shrink: 0;
  align-self: flex-end;
}

.send-button.active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.send-button.active:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4);
}

.send-button.active:active {
  transform: translateY(0);
}

.send-button.stop {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  color: white;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);
  animation: pulse 2s ease-in-out infinite;
}

.send-button.stop:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(239, 68, 68, 0.4);
  background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
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
