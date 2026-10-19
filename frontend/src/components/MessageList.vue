<template>
  <div
    class="message-list-wrapper"
    :style="{
      '--message-font-size': `${fontSize}px`,
      '--message-line-height': lineHeight
    }"
  >
    <!-- 顶部工具栏 -->
    <div v-if="messages.length > 0 && isSelectionMode" class="toolbar">
      <div class="toolbar-left">
        <button 
          @click="toggleSelectionMode" 
          class="btn-toolbar"
        >
          <AppIcon name="times" class=" " />
          取消选择
        </button>
      </div>

      <div class="toolbar-right">
        <button 
          @click="selectAll" 
          class="btn-toolbar btn-select-all"
        >
          <AppIcon name="check-double" class=" " />
          {{ selectedIndices.size === messages.length ? '取消全选' : '全选' }}
        </button>
        
        <button 
          @click="deleteSelected" 
          class="btn-toolbar btn-delete-selected"
          :disabled="selectedIndices.size === 0"
        >
          <AppIcon name="trash" class=" " />
          确认删除 ({{ selectedIndices.size }})
        </button>
      </div>
    </div>

    <div ref="container" class="chat-container" :class="{ 'selection-mode': isSelectionMode, 'has-messages': messages.length > 0 }">
      <!-- 欢迎消息 -->
      <div v-if="messages.length === 0" class="welcome-state">
        <div class="welcome-symbol"><AudioLines :size="32" :stroke-width="1.4" /></div>
        <span class="eyebrow">留一点空间，给新的想法</span>
        <h2>从一句话开始。</h2>
        <p>写下问题，或用声音记录此刻的灵感。<br />剩下的，我们一起梳理。</p>
        <div class="welcome-features"><span><MessageSquare :size="16" />文字对话</span><span><Mic :size="16" />语音输入</span><span><ScanLine :size="16" />截图提问</span></div>
      </div>

      <!-- 消息列表 -->
      <div 
        v-for="(msg, index) in messages" 
        :key="index" 
        class="message mb-6"
        :data-message-index="index"
        :data-message-id="msg.id || msg.local_request_id || ''"
        :class="[
          msg.role === 'user' ? 'user-message' : 'assistant-message',
          { 'selected': selectedIndices.has(index) }
        ]"
      >
        <AnswerVersions v-if="msg.role === 'user' && msg.answer_versions?.length" :versions="msg.answer_versions" />
        <div v-if="msg.role === 'assistant' && msg.scene_name" class="answer-scene-label">场景：{{ msg.scene_name }}</div>
        <template v-if="msg.role === 'user'">
          <!-- 用户消息：复选框在右边 -->
          <div class="message-row">
            <div class="message-content-wrapper">
              <div class="message-bubble user-bubble" @dblclick="handleMessageDoubleClick($event, index, msg.content)">
                <!-- 编辑模式 -->
                <div v-if="editingIndex === index" class="bubble-content editing">
                  <div v-if="willRegenerateAfterEdit" class="regenerate-hint">
                    <AppIcon name="info-circle" class=" " />
                    Enter 保存并重新回答 · Shift+Enter 换行
                  </div>
                  <div v-if="editingAttachments.length" class="message-attachments">
                    <div v-for="attachment in editingAttachments" :key="attachment.id" class="editing-attachment">
                      <button type="button" class="message-attachment-link" aria-label="放大查看截图" @click="openImagePreview(attachment, $event)">
                        <img :src="attachmentUrl(attachment)" alt="消息图片" class="message-attachment-image" />
                      </button>
                      <button type="button" class="remove-attachment" title="移除图片" @click="removeEditingAttachment(attachment.id)">×</button>
                    </div>
                  </div>
                  <button type="button" class="add-attachment" @click="emit('capture-edit-image')">拍照添加</button>
                  <textarea
                    ref="editTextarea"
                    v-model="editingContent"
                    class="edit-textarea"
                    @paste="handleEditPaste"
                    @keydown="handleEditKeyDown($event, index)"
                    @keydown.esc="cancelEdit"
                  ></textarea>
                  <div class="edit-actions">
                    <button @click="saveEdit(index)" class="btn-save" :disabled="isUploadingEditImages || isSavingEdit">
                      <AppIcon name="check" class=" " />
                      {{ willRegenerateAfterEdit ? '保存并重新生成' : '保存' }}
                    </button>
                    <button @click="cancelEdit" class="btn-cancel">
                      <AppIcon name="times" class=" " />
                    </button>
                  </div>
                </div>
                <!-- 正常显示 -->
                <div v-else class="bubble-content">
                  <div v-if="msg.attachments?.length" class="message-attachments">
                    <button
                      v-for="attachment in msg.attachments"
                      :key="attachment.id"
                      type="button"
                      class="message-attachment-link"
                      aria-label="放大查看截图"
                      @click="openImagePreview(attachment, $event)"
                    >
                      <img
                        :src="attachmentUrl(attachment)"
                        alt="笔试题截图"
                        class="message-attachment-image"
                      />
                    </button>
                  </div>
                  <div class="message-text whitespace-pre-wrap" title="双击编辑">{{ msg.content }}</div>
                </div>
                
                <!-- 悬浮操作按钮 - 右下角 -->
                <div v-if="editingIndex !== index && !isSelectionMode" class="message-actions-outer">
                  <button @click="copyMessage(msg, $event)" class="btn-action" title="复制">
                    <AppIcon name="copy" class=" " />
                  </button>
                  <button @click="startEdit(index, msg.content)" class="btn-action" title="编辑">
                    <AppIcon name="edit" class=" " />
                  </button>
                  <button @click="handleDirectRegenerate(msg)" class="btn-action" title="重新生成">
                    <AppIcon name="sync-alt" class=" " />
                  </button>
                  <button @click="enterDeleteMode(index)" class="btn-action btn-delete" title="删除">
                    <AppIcon name="trash" class=" " />
                  </button>
                </div>
              </div>
              <div class="avatar user-avatar">
                <span class="avatar-label">我</span>
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
              <span class="avatar-label">答</span>
            </div>
            <div class="multi-model-messages">
              <div v-if="getFocusedModelIndex(index, msg) !== undefined" class="model-selector-buttons">
                <button
                  v-if="getFocusedModelIndex(index, msg) !== undefined"
                  @click="exitFocused(index)"
                  class="model-selector-btn exit-fullscreen-btn"
                  title="返回并排显示"
                >
                  <AppIcon name="columns" class=" " />
                  显示全部
                </button>

              </div>
              
              <!-- 模型消息卡片容器 -->
              <div
                class="model-view-wrapper"
                :class="{ 'focused-mode': getFocusedModelIndex(index, msg) !== undefined }"
                @mouseenter="setActiveFocusedMessage(index, msg)"
              >
                <button
                  v-if="getFocusedModelIndex(index, msg) !== undefined"
                  @click="navigateModel(index, msg, -1)"
                  class="model-nav-btn model-nav-left"
                  title="切换到上一个模型"
                >
                  <AppIcon name="chevron-left" class=" " />
                </button>
                <div class="model-cards-container" :class="{ 'fullscreen-mode': getFocusedModelIndex(index, msg) !== undefined }">
                  <div 
                    v-for="(modelMsg, modelIndex) in (msg.models || msg.parallel_models || [])" 
                    :key="modelIndex"
                    v-show="getFocusedModelIndex(index, msg) === undefined || getFocusedModelIndex(index, msg) === modelIndex"
                    class="model-message-card"
                    :class="{ 'fullscreen-card': getFocusedModelIndex(index, msg) === modelIndex }"
                    :style="getModelCardStyle(index, msg)"
                    @dblclick="handleMessageDoubleClick($event, index, modelMsg.content, modelIndex)"
                  >
                    <div class="model-card-header">
                      <button type="button" class="model-name-button" title="切换聚焦显示" @click="toggleModelView(index, msg, modelIndex)">{{ getModelDisplayName(modelMsg) }}</button>
                      <ReasoningButtons v-if="!isSelectionMode" :options="reasoningOptions(modelMsg)" :value="defaultEffortForModel(modelMsg)" :disabled="isGenerating" :label="getModelDisplayName(modelMsg) + ' 的思考强度'" @change="rerunSelectedModel(index, msg, modelMsg, $event)" />
                    </div>
                    <!-- 消息内容 -->
                    <div v-if="editingIndex === index && editingModelIndex === modelIndex" class="bubble-content editing">
                      <textarea ref="editTextarea" v-model="editingContent" class="edit-textarea"
                        @keydown="handleEditKeyDown($event, index)" @keydown.esc="cancelEdit" />
                      <div class="edit-actions">
                        <button class="btn-save" :disabled="isSavingEdit || isGenerating" @click="saveEdit(index)">保存</button>
                        <button class="btn-cancel" @click="cancelEdit">取消</button>
                      </div>
                    </div>
                    <div v-else class="bubble-content">
                      <div class="message-text">
                        <ReasoningContent :text="modelMsg.reasoning_content" :streaming="modelMsg.is_streaming" :has-answer="!!modelMsg.content" />
                        <AlgorithmAnswer :content="modelMsg.content" />
                        <div v-if="(isTyping && index === messages.length - 1 && !modelMsg.content) || msg.is_typing_dots" class="flex gap-1 mt-2">
                          <span class="w-2 h-2 rounded-full bg-gray-400 typing-dot"></span>
                          <span class="w-2 h-2 rounded-full bg-gray-400 typing-dot"></span>
                          <span class="w-2 h-2 rounded-full bg-gray-400 typing-dot"></span>
                        </div>
                      </div>
                    </div>
                    
                    <!-- 操作按钮 -->
                    <div v-if="!isSelectionMode" class="message-actions-outer">
                      <button @click="copyMessage(modelMsg, $event)" class="btn-action" title="复制">
                        <AppIcon name="copy" class=" " />
                      </button>
                      <button 
                        v-if="getFocusedModelIndex(index, msg) === undefined"
                        @click="enterFocused(index, msg, modelIndex)" 
                        class="btn-action" 
                        title="聚焦显示"
                      >
                        <AppIcon name="expand" class=" " />
                      </button>
                    </div>
                    <div
                      class="model-card-resize-handle"
                      title="拖拽调整所有多模型卡片宽度"
                      @mousedown.stop.prevent="startCardResize($event)"
                    ></div>
                  </div>
                </div>
                <button
                  v-if="getFocusedModelIndex(index, msg) !== undefined"
                  @click="navigateModel(index, msg, 1)"
                  class="model-nav-btn model-nav-right"
                  title="切换到下一个模型"
                >
                  <AppIcon name="chevron-right" class=" " />
                </button>
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
                <span class="avatar-label">答</span>
              </div>
              <div class="message-bubble assistant-bubble" @dblclick="handleMessageDoubleClick($event, index, msg.content)">
                <!-- 模型标识 -->
                <div v-if="msg.model_info" class="model-badge">
                  <el-tag size="small" effect="plain" :type="getModelTagType(msg.model_info.provider)">
                    {{ msg.model_info.provider && msg.model_info.provider !== 'unknown' ? `${msg.model_info.provider} · ` : '' }}{{ msg.model_info.name }}
                  </el-tag>
                  <ReasoningButtons v-if="!isSelectionMode" :options="reasoningOptions(msg)" :value="defaultEffortForModel(msg)" :disabled="isGenerating" :label="getModelDisplayName(msg) + ' 的思考强度'" @change="rerunSelectedModel(index, msg, msg, $event)" />
                </div>
                
                <!-- 编辑模式 -->
                <div v-if="editingIndex === index" class="bubble-content editing">
                  <div v-if="willRegenerateAfterEdit" class="regenerate-hint">
                    <AppIcon name="info-circle" class=" " />
                    Enter 保存并重新回答 · Shift+Enter 换行
                  </div>
                  <textarea
                    ref="editTextarea"
                    v-model="editingContent"
                    class="edit-textarea"
                    @paste="handleEditPaste"
                    @keydown="handleEditKeyDown($event, index)"
                    @keydown.esc="cancelEdit"
                  ></textarea>
                  <div class="edit-actions">
                    <button @click="saveEdit(index)" class="btn-save" :disabled="isSavingEdit || isGenerating">
                      <AppIcon name="check" class=" " />
                      {{ willRegenerateAfterEdit ? '保存并重新生成' : '保存' }}
                    </button>
                    <button @click="cancelEdit" class="btn-cancel">
                      <AppIcon name="times" class=" " />
                    </button>
                  </div>
                </div>
                <!-- 正常显示 -->
                <div v-else class="bubble-content">
                  <div class="message-text">
                    <ReasoningContent :text="msg.reasoning_content" :streaming="msg.is_streaming" :has-answer="!!msg.content" />
                    <AlgorithmAnswer :content="msg.content" />
                    <div v-if="(isTyping && index === messages.length - 1 && !msg.content) || msg.is_typing_dots" class="flex gap-1 mt-2">
                      <span class="w-2 h-2 rounded-full bg-gray-400 typing-dot"></span>
                      <span class="w-2 h-2 rounded-full bg-gray-400 typing-dot"></span>
                      <span class="w-2 h-2 rounded-full bg-gray-400 typing-dot"></span>
                    </div>
                  </div>
                </div>

                <!-- 悬浮操作按钮 - 右下角 -->
                <div v-if="editingIndex !== index && !isSelectionMode" class="message-actions-outer">
                  <button @click="copyMessage(msg, $event)" class="btn-action" title="复制">
                    <AppIcon name="copy" class=" " />
                  </button>
                  <button @click="startEdit(index, msg.content)" class="btn-action" title="编辑">
                    <AppIcon name="edit" class=" " />
                  </button>
                  <button @click="handleRegenerateAIMessage(index, msg)" class="btn-action" title="重新生成此响应">
                    <AppIcon name="sync-alt" class=" " />
                  </button>
                  <button @click="enterDeleteMode(index)" class="btn-action btn-delete" title="删除">
                    <AppIcon name="trash" class=" " />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
  <Teleport to="body">
    <div
      v-if="previewImageUrl"
      ref="imagePreviewOverlay"
      class="image-preview-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="截图预览，点击图片外侧或按 Esc 关闭"
      tabindex="-1"
      @click.self="closeImagePreview"
    >
      <img :src="previewImageUrl" alt="放大的截图" class="image-preview-full" />
    </div>
  </Teleport>
</template>

<script setup>
import { userStorage, authFetch, privateUrl } from '../utils/auth'

import { AudioLines, MessageSquare, Mic, ScanLine } from 'lucide-vue-next'
import { ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { captureReadingPosition as capturePosition, restoreReadingPosition as restorePosition } from '../utils/scrollPosition'
import { ElMessage } from 'element-plus'
import AnswerVersions from './AnswerVersions.vue'
import ReasoningButtons from './ReasoningButtons.vue'
import ReasoningContent from './ReasoningContent.vue'
import AlgorithmAnswer from './AlgorithmAnswer.vue'
import { clipboardImages, uploadChatImage } from '../utils/imageAttachments'
import { renderMarkdown } from '../utils/markdown'
import { blobToDataUrl, copyRichContent } from '../utils/clipboard'

const props = defineProps({
  messages: {
    type: Array,
    required: true
  },
  isTyping: {
    type: Boolean,
    default: false
  },
  isGenerating: { type: Boolean, default: false },
  currentSessionId: {
    type: String,
    default: null
  },
  sessionConfig: { type: Object, default: null },
  sources: { type: Array, default: () => [] },
  fontSize: {
    type: Number,
    default: 16
  },
  lineHeight: {
    type: Number,
    default: 1.7
  }
})

const emit = defineEmits(['message-updated', 'message-deleted', 'messages-deleted', 'regenerate', 'capture-edit-image'])

const REASONING_OPTIONS = [
  { value: 'none', label: '无' },
  { value: 'minimal', label: '极低' },
  { value: 'low', label: '低' },
  { value: 'medium', label: '中' },
  { value: 'high', label: '高' },
  { value: 'xhigh', label: '极高' }
]

function selectedModel(index, message) {
  const models = getMessageModels(message)
  return models[getFocusedModelIndex(index, message) ?? 0] || models[0]
}

function reasoningOptions(modelMessage) {
  const name = modelMessage?.model_info?.name || modelMessage?.model || ''
  const provider = modelMessage?.model_info?.provider || modelMessage?.source_name || ''
  const source = props.sources.find(item => item.name === provider)
  const identity = `${provider} ${source?.base_url || ''} ${name}`.toLowerCase()
  if (identity.includes('api.xiaomimimo.com')) return [{ value: 'none', label: '关闭思考' }, { value: 'high', label: '开启思考' }]
  if (identity.includes('openrouter')) {
    return REASONING_OPTIONS.filter(option => option.value !== 'none')
  }
  if (identity.includes('qwen') || identity.includes('dashscope.aliyuncs.com')) {
    return REASONING_OPTIONS.filter(option => ['none', 'low', 'medium', 'xhigh'].includes(option.value))
  }
  if (
    identity.includes('api.openai.com') && /^(gpt-[56]|o[134](?:-|$))/i.test(name)
  ) return REASONING_OPTIONS
  return REASONING_OPTIONS.slice(0, 1)
}

function defaultEffortForModel(modelMessage) {
  const model = getModelFullName(modelMessage)
  const configured = modelMessage?.model_info?.reasoning_effort || props.sessionConfig?.model_targets?.find(target => (
    `${target.source_name}::${target.model}` === model
  ))?.reasoning_effort
  const allowed = reasoningOptions(modelMessage)
  return allowed.some(option => option.value === configured) ? configured : allowed[0].value
}

function rerunSelectedModel(index, message, targetModel = null, effort) {
  if (props.isGenerating) return
  const modelMessage = targetModel || (message.model_info ? message : selectedModel(index, message))
  const model = getModelFullName(modelMessage)
  const parent = props.messages.find(item => item.id === message.parent_id)
    || [...props.messages.slice(0, index)].reverse().find(item => item.role === 'user')
  if (!model || !parent?.id) {
    ElMessage.error('找不到该回答关联的模型或问题')
    return
  }
  const allowed = reasoningOptions(modelMessage)
  if (!allowed.some(option => option.value === effort) || effort === defaultEffortForModel(modelMessage)) return
  emit('regenerate', {
    messageId: parent.id,
    newContent: parent.content,
    model,
    reasoningEffort: allowed.some(option => option.value === effort) ? effort : allowed[0].value,
    targeted: true
  })
}

function attachmentUrl(attachment) {
  if (!props.currentSessionId || !attachment?.id) return ''
  return privateUrl(`/api/attachments/${encodeURIComponent(props.currentSessionId)}/${encodeURIComponent(attachment.id)}`)
}

const previewImageUrl = ref('')
const imagePreviewOverlay = ref(null)
let imagePreviewTrigger = null

function openImagePreview(attachment, event) {
  const url = attachmentUrl(attachment)
  if (!url) return
  imagePreviewTrigger = event.currentTarget
  previewImageUrl.value = url
  nextTick(() => imagePreviewOverlay.value?.focus())
}

function closeImagePreview() {
  previewImageUrl.value = ''
  const trigger = imagePreviewTrigger
  imagePreviewTrigger = null
  nextTick(() => trigger?.isConnected && trigger.focus())
}

watch(() => props.currentSessionId, () => {
  previewImageUrl.value = ''
  imagePreviewTrigger = null
  if (editingIndex.value !== null) cancelEdit()
})

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
  const shortName = fullName.includes('/') ? fullName.split('/').pop() : fullName
  const sourceName = modelMsg.model_info?.provider || modelMsg.source_name
  return sourceName && sourceName !== 'unknown'
    ? `${sourceName} · ${shortName}`
    : shortName
}

function getModelFullName(modelMsg) {
  const explicitId = modelMsg?.model_info?.id || modelMsg?.model_key
  if (explicitId) return explicitId
  const model = modelMsg?.model_info?.name || modelMsg?.model || ''
  const source = modelMsg?.model_info?.provider || modelMsg?.source_name
  return source && source !== 'unknown' ? `${source}::${model}` : model
}

function getMessageModels(msg) {
  return msg.models || msg.parallel_models || []
}

function getPreferredModelIndex(msg) {
  const models = getMessageModels(msg)
  if (models.length === 0) return undefined
  
  const defaultModel = multiModelPreferences.value.defaultModel
  if (defaultModel) {
    const index = models.findIndex(modelMsg => (
      getModelFullName(modelMsg) === defaultModel
      || modelMsg?.model_info?.name === defaultModel
      || modelMsg?.model === defaultModel
    ))
    if (index >= 0) return index
  }
  
  return 0
}

function getFocusedModelIndex(messageIndex, msg) {
  if (Object.prototype.hasOwnProperty.call(fullscreenModelIndex.value, messageIndex)) {
    const value = fullscreenModelIndex.value[messageIndex]
    return value === null ? undefined : value
  }
  
  if (multiModelPreferences.value.displayMode === 'focused') {
    return getPreferredModelIndex(msg)
  }
  
  return undefined
}

function getModelCardStyle(messageIndex, msg) {
  const width = Number(multiModelPreferences.value.cardWidth)
  const focused = getFocusedModelIndex(messageIndex, msg) !== undefined
  
  if (!width && focused) {
    return {
      flex: '0 1 auto',
      width: '860px',
      maxWidth: '100%'
    }
  }
  
  if (!width) return {}
  
  return {
    // Parallel cards must stay on the same row. The saved width remains the
    // preferred width, but flex-shrink may reduce it when the row is narrower.
    flex: focused ? '0 1 auto' : `0 1 ${width}px`,
    width: `${width}px`,
    maxWidth: focused ? '100%' : undefined
  }
}

const container = ref(null)
const editTextarea = ref(null)

// 编辑相关
const editingIndex = ref(null)
const editingModelIndex = ref(null)
const editingContent = ref('')
const isSavingEdit = ref(false)
const editingAttachments = ref([])
const isUploadingEditImages = ref(false)
const newEditingImageIds = new Set()
const editingSessionId = ref(null)
let editUploadVersion = 0
let editingImageUploads = 0

function releaseUnusedEditingImage(id, sessionId = editingSessionId.value) {
  if (!sessionId || !id) return
  authFetch(privateUrl(`/api/attachments/${encodeURIComponent(sessionId)}/${encodeURIComponent(id)}`), {
    method: 'DELETE'
  }).catch(error => console.warn('清理未使用图片失败:', error))
}

function discardNewEditingImages() {
  for (const id of newEditingImageIds) releaseUnusedEditingImage(id)
  newEditingImageIds.clear()
}

function removeEditingAttachment(id) {
  if (newEditingImageIds.has(id)) {
    releaseUnusedEditingImage(id)
    newEditingImageIds.delete(id)
  }
  editingAttachments.value = editingAttachments.value.filter(item => item.id !== id)
}

function addCapturedEditingImage(attachment, sessionId) {
  if (editingIndex.value === null || props.currentSessionId !== sessionId) return false
  newEditingImageIds.add(attachment.id)
  editingAttachments.value.push(attachment)
  return true
}

async function handleEditPaste(event) {
  if (props.messages[editingIndex.value]?.role !== 'user') return
  const files = clipboardImages(event.clipboardData)
  if (!files.length) return
  event.preventDefault()
  await addEditingImages(files)
}

async function addEditingImages(files) {
  if (!props.currentSessionId || !files.length) return
  const version = editUploadVersion
  const sessionId = props.currentSessionId
  editingImageUploads++
  isUploadingEditImages.value = true
  try {
    for (const file of files) {
      const attachment = await uploadChatImage(file, sessionId)
      if (version !== editUploadVersion || sessionId !== props.currentSessionId) {
        releaseUnusedEditingImage(attachment.id, sessionId)
        return
      }
      newEditingImageIds.add(attachment.id)
      editingAttachments.value.push(attachment)
    }
  } catch (error) {
    ElMessage.error(error.message || '粘贴图片失败')
  } finally {
    editingImageUploads--
    isUploadingEditImages.value = editingImageUploads > 0
  }
}

// 选择相关
const isSelectionMode = ref(false)
const selectedIndices = ref(new Set())

const MULTI_MODEL_PREFERENCES_KEY = 'multiModelDisplayPreferences'
const DEFAULT_MULTI_MODEL_PREFERENCES = {
  displayMode: 'parallel',
  defaultModel: '',
  cardWidth: 0
}

const multiModelPreferences = ref({ ...DEFAULT_MULTI_MODEL_PREFERENCES })

// 聚焦模式相关 - 记录每个消息的聚焦模型索引，null 表示本条消息临时显示全部
const fullscreenModelIndex = ref({})
const activeFocusedMessageIndex = ref(null)
const resizeState = ref(null)

function loadMultiModelPreferences() {
  try {
    const raw = userStorage.getItem(MULTI_MODEL_PREFERENCES_KEY)
    if (!raw) {
      multiModelPreferences.value = { ...DEFAULT_MULTI_MODEL_PREFERENCES }
      return
    }
    multiModelPreferences.value = {
      ...DEFAULT_MULTI_MODEL_PREFERENCES,
      ...JSON.parse(raw)
    }
  } catch (error) {
    console.warn('加载多模型显示偏好失败:', error)
    multiModelPreferences.value = { ...DEFAULT_MULTI_MODEL_PREFERENCES }
  }
}

function saveMultiModelPreferences() {
  userStorage.setItem(MULTI_MODEL_PREFERENCES_KEY, JSON.stringify(multiModelPreferences.value))
  window.dispatchEvent(new CustomEvent('multi-model-preferences-updated', {
    detail: multiModelPreferences.value
  }))
}

function handlePreferencesUpdated(event) {
  if (event.detail) {
    multiModelPreferences.value = {
      ...DEFAULT_MULTI_MODEL_PREFERENCES,
      ...event.detail
    }
  } else {
    loadMultiModelPreferences()
  }
}

// 监听消息数量变化，如果消息为空，自动退出选择模式
watch(() => props.messages.length, (newCount) => {
  if (newCount === 0) {
    isSelectionMode.value = false
    selectedIndices.value.clear()
  }
})

// 开始编辑
function handleMessageDoubleClick(event, index, content, modelIndex = null) {
  if (event.target.closest('button, a, input, textarea, select, .model-card-resize-handle')) return
  if (editingIndex.value === index && editingModelIndex.value === modelIndex) return
  startEdit(index, content, modelIndex)
}

function startEdit(index, content, modelIndex = null) {
  if (isSelectionMode.value || isSavingEdit.value) return
  willRegenerateAfterEdit.value = props.messages[index]?.role === 'user'
  editUploadVersion++
  discardNewEditingImages()
  editingIndex.value = index
  editingModelIndex.value = modelIndex
  editingSessionId.value = props.currentSessionId
  editingContent.value = content
  editingAttachments.value = [...(props.messages[index]?.attachments || [])]
  nextTick(() => {
    const textarea = Array.isArray(editTextarea.value) ? editTextarea.value.find(element => element?.isConnected) : editTextarea.value
    if (!textarea) return
    textarea.focus()
    textarea.setSelectionRange(textarea.value.length, textarea.value.length)
    textarea.style.height = 'auto'
    textarea.style.height = textarea.scrollHeight + 'px'
    textarea.scrollTop = textarea.scrollHeight
  })
}

// 编辑模式下的重新生成标志
const willRegenerateAfterEdit = ref(false)

function handleEditKeyDown(event, index) {
  // Enter confirms an IME candidate without submitting the message.
  if (event.isComposing || event.keyCode === 229) return
  if (event.key !== 'Enter' || event.shiftKey) return
  event.preventDefault()
  event.stopPropagation()
  saveEdit(index)
}

// 保存用户问题后，使用现有接口保存修改并流式重新回答。
async function saveEdit(index) {
  if (editingIndex.value !== index || isUploadingEditImages.value || isSavingEdit.value) return
  if (props.isGenerating && !willRegenerateAfterEdit.value) return ElMessage.warning('请修改问题重新生成，或停止生成后编辑回答正文')
  if (!editingContent.value.trim() && !editingAttachments.value.length) {
    ElMessage.warning('消息内容不能为空')
    return
  }

  isSavingEdit.value = true
  try {
    const message = props.messages[index]
    const messageId = message.id
    const newContent = editingContent.value.trim()
    const attachmentIds = message.role === 'user'
      ? editingAttachments.value.map(item => item.id)
      : undefined
    
    // 如果标记为需要重新生成，则触发重新生成
    if (willRegenerateAfterEdit.value && message.role === 'user') {
      editingIndex.value = null
      editingModelIndex.value = null
      editingContent.value = ''
      editingAttachments.value = []
      willRegenerateAfterEdit.value = false
      newEditingImageIds.clear()
      editingSessionId.value = null
      
      // 触发重新生成
      emit('regenerate', { messageId, messageIndex: index, newContent, attachmentIds })
      return
    }
    
    // 否则只是更新消息
    const response = await authFetch(`/api/sessions/${props.currentSessionId}/messages/${messageId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        content: newContent,
        attachment_ids: attachmentIds,
        ...(editingModelIndex.value !== null ? { model_key: getModelFullName(getMessageModels(message)[editingModelIndex.value]) } : {})
      })
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || '更新失败')
    }

    emit('message-updated')
    editingIndex.value = null
    editingModelIndex.value = null
    editingContent.value = ''
    editingAttachments.value = []
    newEditingImageIds.clear()
    editingSessionId.value = null
  } catch (error) {
    console.error('保存编辑失败:', error)
    ElMessage.error(`保存失败: ${error.message}`)
  } finally {
    isSavingEdit.value = false
  }
}

// 取消编辑
function cancelEdit() {
  editUploadVersion++
  discardNewEditingImages()
  editingIndex.value = null
  editingModelIndex.value = null
  editingSessionId.value = null
  editingContent.value = ''
  editingAttachments.value = []
  willRegenerateAfterEdit.value = false
}

function clipboardMarkdownHtml(content) {
  const container = document.createElement('div')
  container.innerHTML = renderMarkdown(content || '')
  container.querySelectorAll('.copy-button').forEach(button => button.remove())
  return container.innerHTML
}

async function buildAttachmentCopyData(attachments = []) {
  const results = []
  for (const [index, attachment] of attachments.entries()) {
    const relativeUrl = attachmentUrl(attachment)
    if (!relativeUrl) continue
    const absoluteUrl = new URL(relativeUrl, window.location.origin).href
    let imageUrl = absoluteUrl
    try {
      const response = await authFetch(relativeUrl)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      imageUrl = await blobToDataUrl(await response.blob())
    } catch (error) {
      console.warn('内嵌复制图片失败，保留图片链接:', error)
    }
    results.push({
      label: `截图 ${index + 1}`,
      absoluteUrl,
      imageUrl
    })
  }
  return results
}

// 复制消息（用户截图会以内嵌富文本图片写入剪贴板）
async function copyMessage(message, event) {
  const button = event?.currentTarget
  try {
    const content = typeof message === 'string' ? message : (message?.content || '')
    const attachments = typeof message === 'object' ? (message?.attachments || []) : []
    const copiedImages = attachments.length ? await buildAttachmentCopyData(attachments) : []
    const imageText = copiedImages.map(image => `![${image.label}](${image.absoluteUrl})`).join('\n')
    const text = [content, imageText].filter(Boolean).join('\n\n')
    const imagesHtml = copiedImages.map(image => (
      `<p><img src="${image.imageUrl}" alt="${image.label}" style="max-width:100%;height:auto;" /></p>`
    )).join('')
    const html = `<div>${clipboardMarkdownHtml(content)}${imagesHtml}</div>`
    await copyRichContent(text, html)
    // 可以添加一个简单的提示
    if (button?.isConnected) {
      const originalHTML = button.innerHTML
      button.innerHTML = '<AppIcon name="check" class=" " />'
      setTimeout(() => {
        if (button.isConnected) button.innerHTML = originalHTML
      }, 1000)
    }
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
    
    const response = await authFetch(`/api/sessions/${props.currentSessionId}/messages/delete`, {
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

function toggleModelView(messageIndex, msg, modelIndex) {
  if (getFocusedModelIndex(messageIndex, msg) === modelIndex) {
    exitFocused(messageIndex)
  } else {
    enterFocused(messageIndex, msg, modelIndex)
  }
}

function enterFocused(messageIndex, msg, modelIndex) {
  const models = getMessageModels(msg)
  const modelName = getModelFullName(models[modelIndex])
  
  fullscreenModelIndex.value[messageIndex] = modelIndex

  fullscreenModelIndex.value = { ...fullscreenModelIndex.value }
  activeFocusedMessageIndex.value = messageIndex
  
  if (modelName) {
    multiModelPreferences.value.defaultModel = modelName
    saveMultiModelPreferences()
  }
}

function exitFocused(messageIndex) {
  fullscreenModelIndex.value[messageIndex] = null
  const message = props.messages[messageIndex]

  fullscreenModelIndex.value = { ...fullscreenModelIndex.value }
  if (activeFocusedMessageIndex.value === messageIndex) {
    activeFocusedMessageIndex.value = null
  }
}

function navigateModel(messageIndex, msg, direction) {
  const models = getMessageModels(msg)
  if (models.length === 0) return
  
  const currentIndex = getFocusedModelIndex(messageIndex, msg) ?? getPreferredModelIndex(msg) ?? 0
  const nextIndex = (currentIndex + direction + models.length) % models.length
  enterFocused(messageIndex, msg, nextIndex)
}

function setActiveFocusedMessage(messageIndex, msg) {
  if (getFocusedModelIndex(messageIndex, msg) !== undefined) {
    activeFocusedMessageIndex.value = messageIndex
  }
}

function isEditableTarget(target) {
  if (!target) return false
  const tagName = target.tagName?.toLowerCase()
  return tagName === 'input' || tagName === 'textarea' || target.isContentEditable
}

function findKeyboardTargetMessageIndex() {
  const activeIndex = activeFocusedMessageIndex.value
  if (
    activeIndex !== null
    && props.messages[activeIndex]
    && getFocusedModelIndex(activeIndex, props.messages[activeIndex]) !== undefined
  ) {
    return activeIndex
  }
  
  for (let index = props.messages.length - 1; index >= 0; index--) {
    const msg = props.messages[index]
    if (
      msg?.role !== 'user'
      && (msg?.is_multi_model || msg?.type === 'multi_model' || msg?.parallel_models)
      && getFocusedModelIndex(index, msg) !== undefined
    ) {
      return index
    }
  }
  
  return null
}

function handleModelKeyboardNavigation(event) {
  if (previewImageUrl.value) {
    if (event.key === 'Escape') {
      event.preventDefault()
      closeImagePreview()
    }
    return
  }
  if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
  if (isEditableTarget(event.target)) return
  
  const messageIndex = findKeyboardTargetMessageIndex()
  if (messageIndex === null) return
  
  const msg = props.messages[messageIndex]
  event.preventDefault()
  navigateModel(messageIndex, msg, event.key === 'ArrowLeft' ? -1 : 1)
}

function startCardResize(event) {
  const card = event.currentTarget.closest('.model-message-card')
  const currentWidth = Number(multiModelPreferences.value.cardWidth) || card?.getBoundingClientRect().width || 420
  const isFocused = card?.classList.contains('fullscreen-card')
  
  resizeState.value = {
    startX: event.clientX,
    startWidth: currentWidth,
    factor: isFocused ? 2 : 1
  }
  document.body.classList.add('resizing-model-card')
}

function handleCardResize(event) {
  if (!resizeState.value) return
  
  const delta = (event.clientX - resizeState.value.startX) * resizeState.value.factor
  const maxWidth = Math.max(320, Math.min(window.innerWidth - 160, 1400))
  const width = Math.round(Math.min(Math.max(resizeState.value.startWidth + delta, 320), maxWidth))
  multiModelPreferences.value.cardWidth = width
}

function stopCardResize() {
  if (!resizeState.value) return
  
  resizeState.value = null
  document.body.classList.remove('resizing-model-card')
  saveMultiModelPreferences()
}

onMounted(() => {
  loadMultiModelPreferences()
  window.addEventListener('multi-model-preferences-updated', handlePreferencesUpdated)
  window.addEventListener('mousemove', handleCardResize)
  window.addEventListener('mouseup', stopCardResize)
  window.addEventListener('keydown', handleModelKeyboardNavigation)
})

onBeforeUnmount(() => {
  previewImageUrl.value = ''
  window.removeEventListener('multi-model-preferences-updated', handlePreferencesUpdated)
  window.removeEventListener('mousemove', handleCardResize)
  window.removeEventListener('mouseup', stopCardResize)
  window.removeEventListener('keydown', handleModelKeyboardNavigation)
  document.body.classList.remove('resizing-model-card')
})

function scrollToMessage(index) {
  const message = container.value?.querySelector(`[data-message-index="${index}"]`)
  message?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

defineExpose({
  captureReadingPosition: () => capturePosition(container.value),
  restoreReadingPosition: position => restorePosition(container.value, position),
  scrollToMessage,
  addCapturedEditingImage
})
</script>

<style scoped>
.answer-scene-label { color:#64748b; font-size:12px; margin:4px 0 8px 40px; }
.message-list-wrapper {
  --message-font-size: 16px;
  --message-line-height: 1.7;
  width: 100%;
  height: 100%;
  min-height: 0;
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
  min-height: 0;
  box-sizing: border-box;
  width: 100%;
  max-width: 1280px;
  margin: 0 auto;
  padding: 28px 32px 48px;
  overflow-y: auto;
  overflow-x: hidden;
  scroll-behavior: auto;
  scrollbar-gutter: stable;
  background: #f7f9fc;
}

.chat-container.has-messages::after {
  content: '';
  display: block;
  height: clamp(180px, 42vh, 560px);
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
  animation: none;
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
  justify-content: flex-start;
}

.message-bubble {
  max-width: min(78%, 920px);
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
  padding: 13px 17px;
  border-radius: 16px;
  line-height: 1.6;
  position: relative;
}

.bubble-content.editing {
  padding: 16px;
  width: 100%;
  max-width: none;
}

.user-bubble .bubble-content {
  background: #eef5ff;
  color: #172033;
  border: 1px solid #cfe0fb;
  border-bottom-right-radius: 5px;
  box-shadow: 0 2px 8px rgba(37, 99, 235, .06);
  font-weight: 500;
}

.message-attachments {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 8px;
  margin-bottom: 10px;
}

.editing-attachment { position: relative; min-width: 0; }
.remove-attachment {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 27px;
  height: 27px;
  border: 0;
  border-radius: 50%;
  background: rgba(15, 23, 42, .82);
  color: white;
  cursor: pointer;
  font-size: 19px;
  line-height: 1;
}
.add-attachment {
  display: inline-flex;
  margin-bottom: 10px;
  padding: 6px 11px;
  border: 1px dashed #93c5fd;
  border-radius: 9px;
  color: #2563eb;
  background: #eff6ff;
  cursor: pointer;
  font-size: 13px;
}
.model-card-header { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; padding: 4px 20px 12px; border-bottom: 1px solid #ededed; margin-bottom: 6px; }
.model-name-button { max-width: 100%; border: 0; padding: 0; background: transparent; color: #626262; font-size: 12px; text-align: left; overflow-wrap: anywhere; cursor: pointer; }
.model-name-button:hover { color: #2563eb; }
.model-name-button:focus-visible { outline: 2px solid #93c5fd; outline-offset: 3px; }

.message-attachment-link {
  display: block;
  width: 100%;
  padding: 0;
  overflow: hidden;
  border: 1px solid rgba(59, 130, 246, .2);
  border-radius: 10px;
  background: white;
  cursor: zoom-in;
}

.message-attachment-image {
  display: block;
  width: 100%;
  max-height: 360px;
  object-fit: contain;
  background: #f8fafc;
}

.image-preview-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 28px;
  background: rgba(10, 15, 25, .88);
  cursor: zoom-out;
}

.image-preview-full {
  display: block;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  cursor: default;
}

.assistant-bubble .bubble-content {
  background: white;
  color: #2d3748;
  border-bottom-left-radius: 5px;
  box-shadow: 0 2px 10px rgba(15, 23, 42, .05);
  border: 1px solid #e2e8f0;
}

.model-badge {
  margin: 0 0 6px 2px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}

/* 多模型并行容器 - 横向布局 */
.multi-model-container {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  width: 100%;
  animation: none;
}

.multi-model-messages {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
  min-width: 0;
  padding: 4px;
}

/* 模型卡片容器 - 默认水平并排 */
.model-cards-container {
  display: flex;
  flex-direction: row;
  gap: 12px;
  flex-wrap: nowrap;
  align-items: stretch;
  width: 100%;
  min-width: 0;
}

.model-view-wrapper {
  display: flex;
  align-items: stretch;
  gap: 8px;
  width: 100%;
  min-width: 0;
}

.model-view-wrapper.focused-mode {
  align-items: stretch;
}

.model-view-wrapper.focused-mode .model-cards-container {
  flex: 0 1 auto;
  min-width: 0;
  max-width: 100%;
  justify-content: center;
}

/* 全屏模式 - 垂直布局 */
.model-cards-container.fullscreen-mode {
  flex-direction: column;
  align-items: center;
}

.model-nav-btn {
  flex: 1 1 0;
  min-width: 40px;
  border: 0;
  border-radius: 16px;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  align-self: stretch;
  transition: all 0.2s ease;
  box-shadow: none;
  font-size: 0;
}

.model-nav-btn:hover {
  color: #2563eb;
  background: rgba(239, 246, 255, 0.55);
}

.model-nav-btn i {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  transition: all 0.2s ease;
}

.model-nav-btn:hover i {
  border-color: #93c5fd;
  background: #eff6ff;
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.16);
  transform: scale(1.04);
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
  transition: box-shadow 0.2s ease, border-color 0.2s ease;
  overflow: visible;
}

.model-card-resize-handle {
  position: absolute;
  top: 0;
  right: 0;
  width: 16px;
  height: 100%;
  cursor: ew-resize;
  z-index: 12;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.model-card-resize-handle::after {
  content: '';
  position: absolute;
  top: 18px;
  right: 6px;
  width: 4px;
  height: calc(100% - 36px);
  border-radius: 999px;
  background: #60a5fa;
}

.model-message-card:hover .model-card-resize-handle {
  opacity: 0.5;
}

.model-card-resize-handle:hover {
  opacity: 1 !important;
}

:global(body.resizing-model-card) {
  cursor: ew-resize;
  user-select: none;
}

:global(body.resizing-model-card) .model-message-card {
  transition: none !important;
  transform: none !important;
}

:global(body.resizing-model-card) .model-card-resize-handle {
  opacity: 1 !important;
}

.model-message-card:hover {
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.08), 0 4px 8px rgba(0, 0, 0, 0.04);
  border-color: #cbd5e0;
}

.model-message-card.fullscreen-card {
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
  font-size: var(--message-font-size);
  line-height: var(--message-line-height);
  overflow-wrap: anywhere;
}

.message-text :deep(.markdown-body) {
  font-size: inherit;
  line-height: inherit;
}

.message-text :deep(.markdown-body p),
.message-text :deep(.markdown-body li),
.message-text :deep(.markdown-body blockquote) {
  line-height: inherit;
}

.message-text :deep(.markdown-body h1) {
  font-size: 2em;
}

.message-text :deep(.markdown-body h2) {
  font-size: 1.6em;
}

.message-text :deep(.markdown-body h3) {
  font-size: 1.3em;
}

.message-text :deep(.markdown-body h4),
.message-text :deep(.markdown-body h5),
.message-text :deep(.markdown-body h6) {
  font-size: 1.1em;
}

.message-text :deep(.markdown-body code),
.message-text :deep(.markdown-body pre code) {
  font-size: 0.875em;
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
.btn-save:disabled { opacity: .55; cursor: wait; transform: none; }

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
  width: 34px;
  height: 34px;
  min-width: 34px;
  min-height: 34px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 650;
  letter-spacing: 0;
  position: relative;
  transition: background .18s ease, color .18s ease;
}

.avatar-label {
  line-height: 1;
  transform: translateY(-.5px);
}

@media (max-width: 720px) {
  .chat-container { padding: 20px 12px 36px; }
  .message-row, .message-content-wrapper { gap: 8px; }
  .message-bubble { max-width: calc(100% - 50px); }
  .avatar { width: 32px; height: 32px; min-width: 32px; min-height: 32px; }
  .bubble-content { padding: 11px 14px; }
}

.user-avatar {
  background: #e7effc;
  color: #315c9f;
}

.assistant-avatar {
  background: #e9edf2;
  color: #4b5563;
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
