<template>
  <div class="message-list-wrapper">
    <!-- 顶部工具栏 -->
    <div v-if="messages.length > 0 && isSelectionMode" class="toolbar">
      <div class="toolbar-left">
        <button 
          @click="toggleSelectionMode" 
          class="btn-toolbar"
        >
          <i class="fas fa-times"></i>
          取消选择
        </button>
      </div>

      <div class="toolbar-right">
        <button 
          @click="selectAll" 
          class="btn-toolbar btn-select-all"
        >
          <i class="fas fa-check-double"></i>
          {{ selectedIndices.size === messages.length ? '取消全选' : '全选' }}
        </button>
        
        <button 
          @click="deleteSelected" 
          class="btn-toolbar btn-delete-selected"
          :disabled="selectedIndices.size === 0"
        >
          <i class="fas fa-trash"></i>
          确认删除 ({{ selectedIndices.size }})
        </button>
      </div>
    </div>

    <div ref="container" class="chat-container" :class="{ 'selection-mode': isSelectionMode }">
      <!-- 欢迎消息 -->
      <div v-if="messages.length === 0" class="text-center py-12">
        <i class="fas fa-comments text-6xl text-gray-300 mb-4"></i>
        <h2 class="text-2xl font-semibold text-gray-700 mb-2">开始新对话</h2>
        <p class="text-gray-500">在下方输入消息，或点击右下角的麦克风按钮开始语音输入</p>
        <div class="mt-6 text-sm text-gray-400">
          <p>✨ 支持 Markdown 格式渲染</p>
          <p>🎨 代码高亮显示</p>
          <p>🎤 语音输入识别</p>
        </div>
      </div>

      <!-- 消息列表 -->
      <div 
        v-for="(msg, index) in messages" 
        :key="index" 
        class="message mb-6"
        :class="[
          msg.role === 'user' ? 'user-message' : 'assistant-message',
          { 'selected': selectedIndices.has(index) }
        ]"
      >
        <template v-if="msg.role === 'user'">
          <!-- 用户消息：复选框在右边 -->
          <div class="message-row">
            <div class="message-content-wrapper">
              <div class="message-bubble user-bubble">
                <!-- 编辑模式 -->
                <div v-if="editingIndex === index" class="bubble-content editing">
                  <div v-if="willRegenerateAfterEdit" class="regenerate-hint">
                    <i class="fas fa-info-circle"></i>
                    保存后将删除后续消息并重新生成响应
                  </div>
                  <textarea
                    ref="editTextarea"
                    v-model="editingContent"
                    class="edit-textarea"
                    @keydown.ctrl.enter="saveEdit(index)"
                    @keydown.esc="cancelEdit"
                  ></textarea>
                  <div class="edit-actions">
                    <button @click="saveEdit(index)" class="btn-save">
                      <i class="fas fa-check"></i>
                      {{ willRegenerateAfterEdit ? '保存并重新生成' : '保存' }}
                    </button>
                    <button @click="cancelEdit" class="btn-cancel">
                      <i class="fas fa-times"></i>
                    </button>
                  </div>
                </div>
                <!-- 正常显示 -->
                <div v-else class="bubble-content">
                  <div class="message-text whitespace-pre-wrap">{{ msg.content }}</div>
                </div>
                
                <!-- 悬浮操作按钮 - 右下角 -->
                <div v-if="editingIndex !== index && !isSelectionMode" class="message-actions-outer">
                  <button @click="copyMessage(msg.content, $event)" class="btn-action" title="复制">
                    <i class="fas fa-copy"></i>
                  </button>
                  <button @click="startEdit(index, msg.content)" class="btn-action" title="编辑">
                    <i class="fas fa-edit"></i>
                  </button>
                  <button @click="handleDirectRegenerate(msg)" class="btn-action" title="重新生成">
                    <i class="fas fa-sync-alt"></i>
                  </button>
                  <button @click="enterDeleteMode(index)" class="btn-action btn-delete" title="删除">
                    <i class="fas fa-trash"></i>
                  </button>
                </div>
              </div>
              <div class="avatar user-avatar">
                <i class="fas fa-user"></i>
              </div>
            </div>
            <div v-if="isSelectionMode" class="checkbox-wrapper">
              <input 
                type="checkbox"
                :checked="selectedIndices.has(index)"
                @change="toggleSelect(index)"
                class="message-checkbox"
              />
            </div>
          </div>
        </template>
        
        <template v-else>
          <!-- 多模型并行消息 - 横向排列（流式中 is_multi_model 或已保存的 type='multi_model'）-->
          <div v-if="msg.is_multi_model || msg.type === 'multi_model' || msg.parallel_models" class="multi-model-container">
            <div class="avatar assistant-avatar">
              <i class="fas fa-robot"></i>
            </div>
            <div class="multi-model-messages">
              <!-- 模型选择按钮组 -->
              <div class="model-selector-buttons">
                <button
                  v-for="(modelMsg, modelIndex) in (msg.models || msg.parallel_models || [])"
                  :key="`selector-${modelIndex}`"
                  @click="toggleModelView(index, modelIndex)"
                  class="model-selector-btn"
                  :class="{ 
                    'active': fullscreenModelIndex[index] === modelIndex,
                    'inactive': fullscreenModelIndex[index] !== undefined && fullscreenModelIndex[index] !== modelIndex
                  }"
                >
                  <el-tag 
                    size="small" 
                    effect="plain" 
                    :type="getModelTagType((modelMsg.model_info?.provider || modelMsg.provider || 'unknown'))"
                  >
                    {{ getModelDisplayName(modelMsg) }}
                  </el-tag>
                </button>
                <button
                  v-if="fullscreenModelIndex[index] !== undefined"
                  @click="exitFullscreen(index)"
                  class="model-selector-btn exit-fullscreen-btn"
                  title="返回并排显示"
                >
                  <i class="fas fa-columns"></i>
                  显示全部
                </button>
              </div>
              
              <!-- 模型消息卡片容器 -->
              <div class="model-cards-container" :class="{ 'fullscreen-mode': fullscreenModelIndex[index] !== undefined }">
                <div 
                  v-for="(modelMsg, modelIndex) in (msg.models || msg.parallel_models || [])" 
                  :key="modelIndex"
                  v-show="fullscreenModelIndex[index] === undefined || fullscreenModelIndex[index] === modelIndex"
                  class="model-message-card"
                  :class="{ 'fullscreen-card': fullscreenModelIndex[index] === modelIndex }"
                >
                  <!-- 消息内容 -->
                  <div class="bubble-content">
                    <div class="message-text">
                      <div class="markdown-body" v-html="renderMarkdown(modelMsg.content)"></div>
                      <div v-if="(isTyping && index === messages.length - 1 && !modelMsg.content) || msg.is_typing_dots" class="flex gap-1 mt-2">
                        <span class="w-2 h-2 rounded-full bg-gray-400 typing-dot"></span>
                        <span class="w-2 h-2 rounded-full bg-gray-400 typing-dot"></span>
                        <span class="w-2 h-2 rounded-full bg-gray-400 typing-dot"></span>
                      </div>
                    </div>
                  </div>
                  
                  <!-- 操作按钮 -->
                  <div v-if="!isSelectionMode" class="message-actions-outer">
                    <button @click="copyMessage(modelMsg.content, $event)" class="btn-action" title="复制">
                      <i class="fas fa-copy"></i>
                    </button>
                    <button 
                      v-if="fullscreenModelIndex[index] === undefined"
                      @click="enterFullscreen(index, modelIndex)" 
                      class="btn-action" 
                      title="全屏显示"
                    >
                      <i class="fas fa-expand"></i>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          <!-- 单模型消息 - 原有样式 -->
          <div v-else class="message-row">
            <div v-if="isSelectionMode" class="checkbox-wrapper">
              <input 
                type="checkbox"
                :checked="selectedIndices.has(index)"
                @change="toggleSelect(index)"
                class="message-checkbox"
              />
            </div>
            <div class="message-content-wrapper">
              <div class="avatar assistant-avatar">
                <i class="fas fa-robot"></i>
              </div>
              <div class="message-bubble assistant-bubble">
                <!-- 模型标识 -->
                <div v-if="msg.model_info" class="model-badge">
                  <el-tag size="small" effect="plain" :type="getModelTagType(msg.model_info.provider)">
                    {{ msg.model_info.name }}
                  </el-tag>
                </div>
                
                <!-- 编辑模式 -->
                <div v-if="editingIndex === index" class="bubble-content editing">
                  <div v-if="willRegenerateAfterEdit" class="regenerate-hint">
                    <i class="fas fa-info-circle"></i>
                    保存后将删除后续消息并重新生成响应
                  </div>
                  <textarea
                    ref="editTextarea"
                    v-model="editingContent"
                    class="edit-textarea"
                    @keydown.ctrl.enter="saveEdit(index)"
                    @keydown.esc="cancelEdit"
                  ></textarea>
                  <div class="edit-actions">
                    <button @click="saveEdit(index)" class="btn-save">
                      <i class="fas fa-check"></i>
                      {{ willRegenerateAfterEdit ? '保存并重新生成' : '保存' }}
                    </button>
                    <button @click="cancelEdit" class="btn-cancel">
                      <i class="fas fa-times"></i>
                    </button>
                  </div>
                </div>
                <!-- 正常显示 -->
                <div v-else class="bubble-content">
                  <div class="message-text">
                    <div class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
                    <div v-if="(isTyping && index === messages.length - 1 && !msg.content) || msg.is_typing_dots" class="flex gap-1 mt-2">
                      <span class="w-2 h-2 rounded-full bg-gray-400 typing-dot"></span>
                      <span class="w-2 h-2 rounded-full bg-gray-400 typing-dot"></span>
                      <span class="w-2 h-2 rounded-full bg-gray-400 typing-dot"></span>
                    </div>
                  </div>
                </div>

                <!-- 悬浮操作按钮 - 右下角 -->
                <div v-if="editingIndex !== index && !isSelectionMode" class="message-actions-outer">
                  <button @click="copyMessage(msg.content, $event)" class="btn-action" title="复制">
                    <i class="fas fa-copy"></i>
                  </button>
                  <button @click="startEdit(index, msg.content)" class="btn-action" title="编辑">
                    <i class="fas fa-edit"></i>
                  </button>
                  <button @click="handleRegenerateAIMessage(index, msg)" class="btn-action" title="重新生成此响应">
                    <i class="fas fa-sync-alt"></i>
                  </button>
                  <button @click="enterDeleteMode(index)" class="btn-action btn-delete" title="删除">
                    <i class="fas fa-trash"></i>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { renderMarkdown } from '../utils/markdown'

const props = defineProps({
  messages: {
    type: Array,
    required: true
  },
  isTyping: {
    type: Boolean,
    default: false
  },
  currentSessionId: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['message-updated', 'message-deleted', 'messages-deleted', 'regenerate'])

// 根据 provider 返回不同的标签类型
function getModelTagType(provider) {
  const typeMap = {
    'OpenAI': 'success',
    'OpenRouter': 'primary',
    'Anthropic': 'warning',
    'Google': 'danger',
    'unknown': 'info'
  }
  return typeMap[provider] || 'info'
}

// 提取模型显示名称（去除/前的内容）
function getModelDisplayName(modelMsg) {
  const fullName = modelMsg.model_info?.name || modelMsg.model || '模型'
  // 如果包含/，只返回/后面的内容
  if (fullName.includes('/')) {
    return fullName.split('/').pop()
  }
  return fullName
}

const container = ref(null)
const editTextarea = ref(null)

// 编辑相关
const editingIndex = ref(null)
const editingContent = ref('')

// 选择相关
const isSelectionMode = ref(false)
const selectedIndices = ref(new Set())

// 全屏模式相关 - 记录每个消息的全屏模型索引
const fullscreenModelIndex = ref({})

// 监听消息数量变化，如果消息为空，自动退出选择模式
watch(() => props.messages.length, (newCount) => {
  if (newCount === 0) {
    isSelectionMode.value = false
    selectedIndices.value.clear()
  }
})

// 自动滚动到底部（已禁用，用户可手动滚动）
function scrollToBottom() {
  nextTick(() => {
    if (container.value) {
      container.value.scrollTop = container.value.scrollHeight
    }
  })
}

// 监听消息变化 - 已注释掉自动滚动，避免打断用户阅读
// watch(() => props.messages, scrollToBottom, { deep: true })
// watch(() => props.isTyping, scrollToBottom)

// 开始编辑
function startEdit(index, content) {
  editingIndex.value = index
  editingContent.value = content
  nextTick(() => {
    if (editTextarea.value && editTextarea.value.length > 0) {
      editTextarea.value[0].focus()
      editTextarea.value[0].style.height = 'auto'
      editTextarea.value[0].style.height = editTextarea.value[0].scrollHeight + 'px'
    }
  })
}

// 编辑模式下的重新生成标志
const willRegenerateAfterEdit = ref(false)

// 保存编辑
async function saveEdit(index) {
  if (!editingContent.value.trim()) {
    ElMessage.warning('消息内容不能为空')
    return
  }

  try {
    const message = props.messages[index]
    const messageId = message.id || `msg_${index}`
    const newContent = editingContent.value.trim()
    
    // 如果标记为需要重新生成，则触发重新生成
    if (willRegenerateAfterEdit.value && message.role === 'user') {
      editingIndex.value = null
      editingContent.value = ''
      willRegenerateAfterEdit.value = false
      
      // 触发重新生成
      emit('regenerate', { messageId, newContent })
      return
    }
    
    // 否则只是更新消息
    const response = await fetch(`/api/sessions/${props.currentSessionId}/messages/${messageId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        content: newContent
      })
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || '更新失败')
    }

    emit('message-updated')
    editingIndex.value = null
    editingContent.value = ''
  } catch (error) {
    console.error('保存编辑失败:', error)
    ElMessage.error(`保存失败: ${error.message}`)
  }
}

// 取消编辑
function cancelEdit() {
  editingIndex.value = null
  editingContent.value = ''
  willRegenerateAfterEdit.value = false
}

// 复制消息
async function copyMessage(content, event) {
  try {
    await navigator.clipboard.writeText(content)
    // 可以添加一个简单的提示
    const btn = event.currentTarget
    const originalHTML = btn.innerHTML
    btn.innerHTML = '<i class="fas fa-check"></i>'
    setTimeout(() => {
      btn.innerHTML = originalHTML
    }, 1000)
  } catch (error) {
    console.error('复制失败:', error)
    ElMessage.error('复制失败，请重试')
  }
}

// 切换选择模式
function toggleSelectionMode() {
  isSelectionMode.value = !isSelectionMode.value
  if (!isSelectionMode.value) {
    selectedIndices.value.clear()
  }
}

// 进入删除模式（点击单个删除图标时触发）
function enterDeleteMode(index) {
  isSelectionMode.value = true
  selectedIndices.value.add(index)
}

// 删除单条消息
async function deleteMessage(index) {
  await deleteMessages([index])
}

// 切换选择
function toggleSelect(index) {
  if (selectedIndices.value.has(index)) {
    selectedIndices.value.delete(index)
  } else {
    selectedIndices.value.add(index)
  }
}

// 全选/取消全选
function selectAll() {
  if (selectedIndices.value.size === props.messages.length) {
    selectedIndices.value.clear()
  } else {
    selectedIndices.value = new Set(props.messages.map((_, i) => i))
  }
}

// 删除选中的消息
async function deleteSelected() {
  if (selectedIndices.value.size === 0) {
    return
  }

  const indices = Array.from(selectedIndices.value).sort((a, b) => a - b)
  await deleteMessages(indices)
}

// 统一的删除方法
async function deleteMessages(indices) {
  if (!indices || indices.length === 0) {
    return
  }

  try {
    // 将索引转换为消息ID
    const messageIds = indices.map(index => {
      const message = props.messages[index]
      return message.id || `msg_${index}` // 兼容旧数据
    })
    
    const response = await fetch(`/api/sessions/${props.currentSessionId}/messages/delete`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        message_ids: messageIds  // 使用消息ID而不是索引
      })
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || '删除失败')
    }

    emit('messages-deleted')
    selectedIndices.value.clear()
  } catch (error) {
    console.error('删除消息失败:', error)
    ElMessage.error(`删除失败: ${error.message}`)
  }
}

// 直接重新生成用户消息（不修改内容）
function handleDirectRegenerate(message) {
  if (message.role !== 'user') {
    ElMessage.warning('只能重新生成用户消息的响应')
    return
  }
  
  if (!message.id) {
    ElMessage.error('消息ID不存在')
    return
  }
  
  // 直接触发重新生成，使用原消息内容
  emit('regenerate', { 
    messageId: message.id, 
    newContent: message.content  // 使用原内容
  })
}

// 重新生成 AI 消息（找到它的父消息并重新生成）
function handleRegenerateAIMessage(index, message) {
  if (message.role !== 'assistant') {
    ElMessage.warning('此功能仅用于重新生成 AI 响应')
    return
  }
  
  // 找到父消息（用户消息）
  const parentId = message.parent_id
  if (!parentId) {
    // 如果没有 parent_id，尝试找到前一条用户消息
    for (let i = index - 1; i >= 0; i--) {
      if (props.messages[i].role === 'user') {
        const userMsg = props.messages[i]
        if (userMsg.id) {
          emit('regenerate', {
            messageId: userMsg.id,
            newContent: userMsg.content
          })
          return
        }
      }
    }
    ElMessage.error('找不到关联的用户消息')
    return
  }
  
  // 通过 parent_id 找到用户消息
  const userMessage = props.messages.find(m => m.id === parentId)
  if (!userMessage) {
    ElMessage.error('找不到关联的用户消息')
    return
  }
  
  // 触发重新生成
  emit('regenerate', {
    messageId: userMessage.id,
    newContent: userMessage.content
  })
}

// 编辑并重新生成
async function handleRegenerateFromEdit(index, message) {
  if (message.role !== 'user') {
    ElMessage.warning('只能重新生成用户消息的响应')
    return
  }
  
  // 进入编辑模式，并标记为需要重新生成
  willRegenerateAfterEdit.value = true
  startEdit(index, message.content)
}

// 全屏模式相关函数
function toggleModelView(messageIndex, modelIndex) {
  if (fullscreenModelIndex.value[messageIndex] === modelIndex) {
    // 如果点击的是当前全屏的模型，则退出全屏
    exitFullscreen(messageIndex)
  } else {
    // 否则进入该模型的全屏
    enterFullscreen(messageIndex, modelIndex)
  }
}

function enterFullscreen(messageIndex, modelIndex) {
  fullscreenModelIndex.value[messageIndex] = modelIndex
}

function exitFullscreen(messageIndex) {
  delete fullscreenModelIndex.value[messageIndex]
  // 触发响应式更新
  fullscreenModelIndex.value = { ...fullscreenModelIndex.value }
}

defineExpose({
  scrollToBottom
})
</script>

<style scoped>
.message-list-wrapper {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* 工具栏样式 */
.toolbar {
  padding: 8px 24px;
  background: white;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  min-height: 52px;
}

.toolbar-left, .toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.btn-toolbar {
  padding: 6px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s;
  background: white;
  color: #4b5563;
}

.btn-toolbar:hover {
  background: #f9fafb;
  border-color: #d1d5db;
}

.btn-toolbar.active {
  background: #eff6ff;
  color: #3b82f6;
  border-color: #3b82f6;
}

.btn-select-all {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: white;
  border: none;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
}

.btn-select-all:hover {
  background: linear-gradient(135deg, #5568d3 0%, #6a3f8f 100%);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
}

.btn-delete-selected {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  color: white;
  border: none;
  box-shadow: 0 2px 8px rgba(239, 68, 68, 0.3);
}

.btn-delete-selected:hover:not(:disabled) {
  background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
  box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4);
}

.btn-delete-selected:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chat-container {
  flex: 1;
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
  overflow-y: auto;
  overflow-x: hidden;
  scroll-behavior: smooth;
  background: #f8f9fa;
}

.chat-container.selection-mode {
  background: #f0f7ff;
}

/* 滚动条样式 */
.chat-container::-webkit-scrollbar {
  width: 8px;
}

.chat-container::-webkit-scrollbar-track {
  background: transparent;
}

.chat-container::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 4px;
}

.chat-container::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}

.typing-dot {
  animation: typing 1.4s infinite;
}

.typing-dot:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-dot:nth-child(3) {
  animation-delay: 0.4s;
}

/* 消息样式 */
.message {
  animation: fadeInMessage 0.3s ease-out;
}

.message.selected {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.05) 0%, rgba(37, 99, 235, 0.05) 100%);
  border-radius: 16px;
  padding: 8px;
  margin-left: -8px;
  margin-right: -8px;
  border: 1px solid rgba(59, 130, 246, 0.2);
}

.message-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.user-message .message-row {
  flex-direction: row-reverse;
}

.message-content-wrapper {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.user-message .message-content-wrapper {
  flex-direction: row-reverse;
  justify-content: flex-end;
}

.message-bubble {
  max-width: 75%;
  flex-shrink: 1;
  position: relative;
  margin-bottom: 12px;
}

/* 编辑模式下占满宽度 */
.message-bubble:has(.bubble-content.editing) {
  max-width: 95%;
  width: 100%;
}

.bubble-content {
  padding: 14px 18px;
  border-radius: 18px;
  line-height: 1.6;
  position: relative;
}

.bubble-content.editing {
  padding: 16px;
  width: 100%;
  max-width: none;
}

.user-bubble .bubble-content {
  background: transparent;
  color: #1a1a1a;
  border: 2px solid #e5e7eb;
  border-bottom-right-radius: 4px;
  box-shadow: none;
  font-weight: 500;
}

.assistant-bubble .bubble-content {
  background: white;
  color: #2d3748;
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04);
  border: 1px solid #e2e8f0;
}

.model-badge {
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
}

/* 多模型并行容器 - 横向布局 */
.multi-model-container {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  width: 100%;
  animation: fadeInMessage 0.3s ease-out;
}

.multi-model-messages {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
  padding: 4px;
}

/* 模型卡片容器 - 默认水平并排 */
.model-cards-container {
  display: flex;
  flex-direction: row;
  gap: 12px;
  flex-wrap: wrap;
  align-items: stretch;
}

/* 全屏模式 - 垂直布局 */
.model-cards-container.fullscreen-mode {
  flex-direction: column;
}

/* 模型选择按钮组 */
.model-selector-buttons {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.model-selector-btn {
  padding: 6px 14px;
  border: 1.5px solid #dee2e6;
  border-radius: 8px;
  background: white;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  position: relative;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.model-selector-btn::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  opacity: 0;
  transition: opacity 0.3s;
}

.model-selector-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.1);
  border-color: #3b82f6;
}

.model-selector-btn.active {
  border-color: #3b82f6;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.12) 0%, rgba(37, 99, 235, 0.12) 100%);
  box-shadow: 0 3px 10px rgba(59, 130, 246, 0.25);
  color: #3b82f6;
  font-weight: 600;
}

.model-selector-btn.active::before {
  opacity: 0.05;
}

.model-selector-btn.inactive {
  opacity: 0.5;
  transform: scale(0.96);
}

.exit-fullscreen-btn {
  background: linear-gradient(135deg, #495057 0%, #343a40 100%);
  color: white;
  border-color: #495057;
  font-weight: 600;
}

.exit-fullscreen-btn:hover {
  background: linear-gradient(135deg, #343a40 0%, #212529 100%);
  border-color: #343a40;
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.25);
}

.model-message-card {
  flex: 1 1 0;
  min-width: 0;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 10px 0px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04);
  position: relative;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.model-message-card:hover {
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.08), 0 4px 8px rgba(0, 0, 0, 0.04);
  transform: translateY(-3px);
  border-color: #cbd5e0;
}

.model-message-card.fullscreen-card {
  flex: 1 1 100%;
  max-width: 100%;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1), 0 6px 12px rgba(0, 0, 0, 0.06);
  border: 1px solid #cbd5e0;
}

.model-message-card.fullscreen-card::before {
  display: none !important;
}

.model-message-card.fullscreen-card:hover {
  border-color: #cbd5e0 !important;
}

.model-message-card.fullscreen-card:hover::before {
  display: none !important;
  opacity: 0 !important;
}

.message-text {
  width: 100%;
}

/* 消息操作按钮 - 外部悬浮 */
.message-actions-outer {
  position: absolute;
  bottom: -16px;
  right: 0;
  display: flex;
  gap: 4px;
  opacity: 0;  /* 默认隐藏 */
  transition: all 0.2s ease;
  z-index: 10;
  padding: 4px;
  pointer-events: none;  /* 隐藏时不响应鼠标事件 */
}

.message-bubble:hover .message-actions-outer {
  opacity: 1;
  bottom: -20px;
  pointer-events: auto;  /* 显示时响应鼠标事件 */
}

.btn-action {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  color: #64748b;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.btn-action:hover {
  background: white;
  color: #3b82f6;
  border-color: #3b82f6;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
}

.btn-action.btn-delete:hover {
  background: #fef2f2;
  color: #ef4444;
  border-color: #fecaca;
  box-shadow: 0 4px 12px rgba(239, 68, 68, 0.15);
}

/* 编辑相关样式 */
.regenerate-hint {
  padding: 8px 12px;
  background: #fff3cd;
  border: 1px solid #ffc107;
  border-radius: 6px;
  color: #856404;
  font-size: 13px;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.regenerate-hint i {
  font-size: 14px;
}

.edit-textarea {
  width: 100%;
  min-height: 120px;
  padding: 16px;
  border: 2px solid #e2e8f0;
  border-radius: 12px;
  font-size: 15px;
  line-height: 1.7;
  resize: vertical;
  font-family: inherit;
  outline: none;
  background: white;
  color: #1f2937;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  transition: all 0.3s;
}

.edit-textarea:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1), 0 2px 12px rgba(0, 0, 0, 0.08);
}

.user-bubble .edit-textarea {
  background: white;
  color: #1f2937;
}

.edit-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  justify-content: flex-end;
}

.btn-save,
.btn-cancel {
  min-width: 36px;
  height: 36px;
  padding: 0 12px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.2s;
  white-space: nowrap;
}

.btn-save {
  background: #3b82f6;
  color: white;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.25);
}

.btn-save:hover {
  background: #2563eb;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.35);
}

.btn-cancel {
  background: #e2e8f0;
  color: #475569;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.btn-cancel:hover {
  background: #cbd5e0;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

/* 复选框样式 */
.checkbox-wrapper {
  display: flex;
  align-items: flex-start;
  padding-top: 16px;
  flex-shrink: 0;
}

.message-checkbox {
  width: 20px;
  height: 20px;
  cursor: pointer;
  accent-color: #3b82f6;
}

.avatar {
  width: 40px;
  height: 40px;
  min-width: 40px;
  min-height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 18px;
  position: relative;
  transition: all 0.3s ease;
}

.user-avatar {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.25);
}

.user-avatar::before {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: 12px;
  padding: 2px;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  opacity: 0.3;
}

.assistant-avatar {
  background: linear-gradient(135deg, #2d3748 0%, #1a202c 100%);
  color: #f7fafc;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  border: 2px solid #4a5568;
}

.assistant-avatar::after {
  content: '';
  position: absolute;
  top: 2px;
  right: 2px;
  width: 8px;
  height: 8px;
  background: #48bb78;
  border-radius: 50%;
  border: 2px solid #2d3748;
  box-shadow: 0 0 8px rgba(72, 187, 120, 0.6);
}

@keyframes fadeInMessage {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes typing {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.7;
  }
  30% {
    transform: translateY(-10px);
    opacity: 1;
  }
}
</style>
