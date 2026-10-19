<template>
  <div class="chat-view-container" :style="{ '--settings-panel-width': `${settingsPanelWidth}px` }">
    <!-- 会话侧边栏 -->
    <SessionSidebar
      :sessions="sessions"
      :current-session-id="currentSessionId"
      @open-settings="showSettings = true"
      @open-prompt-lab="$emit('open-prompt-lab')"
      @create-session="handleCreateSession"
      @switch-session="handleSwitchSession"
      @delete-session="handleDeleteSession"
      @update-title="handleUpdateTitle"
      @copy-session="handleCopySession"
      @merge-session-audio="handleMergeSessionAudio"
    />
    
    <!-- 主内容区 -->
    <div class="chat-view">
      <!-- 顶部导航栏 -->
      <NavBar :style="{ order: headerPosition === 'top' ? 10 : 90 }"
        :config="config"
        :title="currentSession?.title"
        @open-session-settings="showSessionSettings = true"
      >
        <template #actions>
            <span id="input-settings-controls" class="input-settings-controls"></span>
            <el-button :type="showDoubao ? 'primary' : 'default'" @click="showDoubao = !showDoubao">豆包</el-button>
            <label class="answer-toggle" title="在回答末尾输出 JSON，并显示选择题/判断题答案">
              <input type="checkbox" :checked="currentSession?.session_config?.answer_highlight_enabled"
                :disabled="!currentSessionId || answerToggleBusy || isSending || activeCaptureCount > 0 || sceneSwitching"
                @change="toggleAnswerHighlight($event.target.checked)" />高亮
            </label>
            <span id="answer-highlight-controls" class="answer-highlight-controls"></span>
        </template>
      </NavBar>
      
      <div class="scene-row" :style="{ order: scenePosition === 'top' ? 20 : 80 }">
        <SceneBar :session="currentSession" :disabled="isCapturing" @selected="handleSceneSelected" />
      </div>

      <CaptureButton ref="captureButtonRef"
        :right-click-action="currentSession?.session_config?.right_click_action || 'record'"
        :connected="captureConnected"
        :size="captureButtonSize"
        :loading="isCapturing"
        :disabled="isCapturing"
        @capture="handleCaptureAndSend"
        @cancel="cancelCapture"
      />

      <!-- 主聊天区域 -->
      <div class="chat-main" :style="{ order: 40, '--composer-height': composerHeight + 'px' }">
      <!-- 输入区域 -->
      <InputArea ref="inputAreaRef" class="composer-overlay" :style="{ '--composer-opacity': composerOpacity / 100 }"
        v-model="inputMessage"
        :is-sending="responseBusy"
        :is-stopping="stoppingResponses"
        :is-recording="isRecording"
        :capture-connected="captureConnected"
        :capture-source-name="captureSourceName"
        :capture-mode="captureMode"
        :pending-capture-count="pendingCaptureCount"
        :is-uploading-images="pasteImageUploads > 0"
        :capture-button-size="captureButtonSize"
        @paste-images="handlePasteImages"
        @resize-capture="captureButtonSize = $event"
        :pending-captures="pendingCapturePreviews"
        :capture-responses-active="activeCaptureCount > 0"
        :active-capture-count="activeCaptureCount"
        @send="handleComposerSend"
        @stop="stopAllResponses"
        @reset-capture="handleResetCapture"
        @toggle-capture-mode="toggleCaptureMode"
        @clear-captures="clearPendingCaptures"
        @remove-capture="removePendingCapture"
      >
        <template #layout>
          <label>标题栏<select v-model="headerPosition" aria-label="标题栏位置"><option value="top">顶部</option><option value="bottom">底部</option></select></label>
          <label>场景栏<select v-model="scenePosition" aria-label="场景栏位置"><option value="top">顶部</option><option value="bottom">底部</option></select></label>
          <label>输入框透明度<input type="range" min="0" max="100" v-model.number="composerOpacity" aria-label="输入框背景不透明度" />{{ composerOpacity }}%</label>
        </template>
        <template #capture-source>
          <label>画面来源
            <select :value="captureSourceType" :disabled="isCapturing" @change="changeCaptureSource($event.target.value)">
              <option value="camera">摄像头</option>
              <option value="screen">窗口 / 标签页</option>
            </select>
          </label>
          <label v-if="captureSourceType === 'camera'">设备
            <select :value="selectedCameraId" :disabled="isCapturing" @change="changeCamera($event.target.value)">
              <option value="">自动（UGREEN 2K 优先）</option>
              <option v-for="(camera, index) in cameraDevices" :key="camera.deviceId" :value="camera.deviceId">{{ camera.label || `摄像头 ${index + 1}` }}</option>
              <option v-if="selectedCameraId && !cameraDevices.some(camera => camera.deviceId === selectedCameraId)" :value="selectedCameraId">已选设备（待连接确认）</option>
            </select>
          </label>
          <button type="button" :disabled="isCapturing" @click="handleResetCapture">{{ captureSourceType === 'camera' ? (captureConnected ? '刷新设备' : '连接摄像头') : (captureConnected ? '更换窗口并截图' : '选择窗口并截图') }}</button>
          <button type="button" :disabled="isCapturing || stoppingResponses" @click="handleCaptureAndSend">{{ captureSourceType === 'camera' ? '立即拍照' : '立即截图' }}</button>
          <button v-if="captureConnected" type="button" :disabled="isCapturing" @click="stopCaptureSource">断开</button>
        </template>
        <template #microphone>
          <div class="recording-input-options">
            <div class="recording-mode-summary" role="status">
              <strong>当前模式：{{ recordingModeLabel }}</strong>
              <span>按钮：{{ recordingModeName(buttonRecordingMode, sameRecordingDevice) }} · 右键：{{ recordingModeName(rightClickRecordingMode, sameRecordingDevice) }}</span>
            </div>
            <MicrophoneSelect :key="'mic-' + recordingDeviceRevision" label="麦克风" storage-key="recordingMicrophone" prefer-microphone
              :disabled="isRecording || isProcessingRecording" @change="selectedMicrophone = $event" />
            <MicrophoneSelect :key="'usb-' + recordingDeviceRevision" label="声卡 / 右键" storage-key="recordingUsbInput" prefer-usb
              :disabled="isRecording || isProcessingRecording" @change="selectedUsbInput = $event" />
            <label class="recording-mode-picker">麦克风按钮
              <select v-model="buttonRecordingMode" :disabled="isRecording || isProcessingRecording" aria-label="麦克风按钮采集模式" @change="saveRecordingModes">
                <option value="mix">双路混音</option><option value="microphone">只录麦克风</option><option value="usb">只录声卡</option>
              </select>
            </label>
            <label class="recording-mode-picker">右键
              <select v-model="rightClickRecordingMode" :disabled="isRecording || isProcessingRecording" aria-label="右键采集模式" @change="saveRecordingModes">
                <option value="mix">双路混音</option><option value="microphone">只录麦克风</option><option value="usb">只录声卡</option>
              </select>
            </label>
            <span>{{ recordingDeviceSummary }}</span>
            <span v-if="sameRecordingDevice && (buttonRecordingMode === 'mix' || rightClickRecordingMode === 'mix')" class="recording-device-warning">两路选择了同一设备，混音模式实际只录单路。</span>
            <button type="button" class="recording-defaults" :disabled="isRecording || isProcessingRecording" @click="resetRecordingInputs">恢复默认设备（内置麦克风＋USB 声卡）</button>
          </div>
        </template>
      </InputArea>


        <MessageList 
          :messages="messages"
          :is-typing="isTyping"
          :is-generating="isSending || activeCaptureCount > 0 || sceneSwitching"
          :current-session-id="currentSessionId"
          :session-config="currentSession?.session_config"
          :sources="config.sources"
          :font-size="messageDisplaySettings.fontSize"
          :line-height="messageDisplaySettings.lineHeight"
          ref="messageListRef"
          @message-updated="handleMessageUpdated"
          @message-deleted="handleMessageDeleted"
          @messages-deleted="handleMessageDeleted"
          @regenerate="handleRegenerateMessage"
          @capture-edit-image="handleCaptureForEdit"
        />
        <AnswerHighlight v-if="currentSession?.session_config?.answer_highlight_enabled || currentSession?.session_config?.active_scene?.id === 'written_exam_concise' || currentSession?.session_config?.prompt_template_id === 'written_exam_concise'"
          :key="currentSessionId" :messages="messages"
          @navigate="messageListRef?.scrollToMessage($event)" />
      </div>
      
      <DoubaoRealtimeOverlay v-if="showDoubao" ref="doubaoOverlay" :session="currentSession"
        :recording="isRecording" :draft="inputMessage" @activity="doubaoBusy = $event"
        @close="showDoubao = false" />

      <!-- 可拖动的语音按钮 -->
      <VoiceButton
        :right-click-action="currentSession?.session_config?.right_click_action || 'record'"
        :is-recording="isRecording"
        :audio-level="recordingAudioLevel"
        :phase="recordingPhase"
        :input-source="recordingInputSource"
        :mode-label="recordingModeLabel"
        @toggle="handleToggleRecording('microphone')"
      />
      
      <!-- 设置对话框 -->
      <SettingsModal
        v-if="showSettings"
        :config="config"
        @close="showSettings = false"
        @refresh="handleRefreshConfig"
      />
    </div>

    <!-- 会话设置侧边栏 -->
    <SessionSettingsSidebar
      v-if="showSessionSettings"
      :config="config"
      :session="currentSession"
      @resize="settingsPanelWidth = $event"
      @close="showSessionSettings = false"
      @updated="handleSessionConfigUpdated"
    />
  </div>
</template>

<script setup>
import { userStorage, authFetch, privateUrl } from '../utils/auth'

import { preferredRecordingDevice } from '../utils/recordingDevices'
import { recordingRoute, recordingModeName, RECORDING_MODES } from '../utils/recordingRoute'
import { beginTargetedAnswer, appendAnswerDelta } from '../utils/answerStream'
import { bindStreamingQuestion, editedQuestionReference, resolveEditedQuestionId, findEditedQuestionIndex } from '../utils/streamingQuestion'
import { ref, onMounted, onUnmounted, watch, computed, nextTick } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import NavBar from '../components/NavBar.vue'
import MessageList from '../components/MessageList.vue'
import InputArea from '../components/InputArea.vue'
import MicrophoneSelect from '../components/MicrophoneSelect.vue'
import SceneBar from '../components/SceneBar.vue'
import AnswerHighlight from '../components/AnswerHighlight.vue'
import DoubaoRealtimeOverlay from '../components/DoubaoRealtimeOverlay.vue'
import CaptureButton from '../components/CaptureButton.vue'
import VoiceButton from '../components/VoiceButton.vue'
import SettingsModal from '../components/SettingsModal.vue'
import SessionSidebar from '../components/SessionSidebar.vue'
import SessionSettingsSidebar from '../components/SessionSettingsSidebar.vue'
import api from '../utils/api'
import { createEscapeGesture } from '../utils/escapeGesture'
import { installMicrophoneContextMenu } from '../utils/microphoneContextMenu'
import { interruptAnswerStreams } from '../utils/interruptAnswerStreams'
import { uploadChatImage } from '../utils/imageAttachments'
import { blobToDataUrl, copyImageBlob, copyRichContent } from '../utils/clipboard'
import { renderMarkdown } from '../utils/markdown'
import { DisplayScreenCapture } from '../utils/screenCapture'
import { CameraCapture } from '../utils/cameraCapture'

defineEmits(['open-prompt-lab'])
const showDoubao = ref(true), doubaoOverlay = ref(null)
let recordingWithDoubao = false

const captureButtonSize = ref(64)
try {
  const savedSize = Number(userStorage.getItem('captureButtonSize'))
  if (Number.isFinite(savedSize) && savedSize >= 40 && savedSize <= 120) captureButtonSize.value = savedSize
} catch {}
watch(captureButtonSize, size => { try { userStorage.setItem('captureButtonSize', String(size)) } catch {} })
const pasteImageUploads = ref(0)
let pasteImageVersion = 0
async function handlePasteImages(files) {
  const sessionId = currentSessionId.value
  if (!sessionId) return ElMessage.warning('请先创建会话')
  const version = pasteImageVersion
  pasteImageUploads.value++
  try {
    for (const file of files) {
      const attachment = await uploadChatImage(file, sessionId)
      if (version !== pasteImageVersion || currentSessionId.value !== sessionId) {
        releaseUnusedCapture(sessionId, attachment.id)
        return
      }
      pendingCaptures.value.push(attachment)
    }
  } catch (error) { ElMessage.error(error.message || '粘贴图片失败') }
  finally { pasteImageUploads.value-- }
}

const answerToggleBusy = ref(false)
async function toggleAnswerHighlight(enabled) {
  const session = currentSession.value
  if (!session || answerToggleBusy.value) return
  answerToggleBusy.value = true
  try {
    const result = await api.put(`/sessions/${session.id}/config`, {
      ...session.session_config, answer_highlight_enabled: enabled
    })
    if (result.config?.answer_highlight_enabled !== enabled) {
      throw new Error('后端未加载答案高亮功能，请重启后端服务')
    }
    session.session_config = result.config
  } catch (error) {
    ElMessage.error('答案高亮设置失败：' + (error.response?.data?.detail || error.message))
  } finally { answerToggleBusy.value = false }
}
const sceneSwitching = ref(false)
const captureControllers = new Set()
const restartingResponse = ref(false)
let restartVersion = 0
let pendingSceneChange = null
let sceneChangeVersion = 0
function streamController() {
  const controller = new AbortController()
  controller.finished = new Promise(resolve => { controller.finish = resolve })
  return controller
}
async function handleSceneSelected(change) {
  const version = ++sceneChangeVersion
  pendingSceneChange?.onSettled?.()
  pendingSceneChange = { ...change, version }
  const running = abortController.value
  if (running) running.abort('scene-switch')
  for (const controller of captureControllers) controller.abort('scene-switch')
  if (sceneSwitching.value) return
  sceneSwitching.value = true
  try {
    while (pendingSceneChange) {
      await Promise.all([...captureControllers].map(controller => controller.finished))
      const active = abortController.value
      if (active) { active.abort('scene-switch'); await active.finished }
      const request = pendingSceneChange
      pendingSceneChange = null
      try {
        const latest = await api.get(`/sessions/${request.sessionId}`)
        if (request.version !== sceneChangeVersion) continue
        const config = { ...latest.session_config, active_scene: request.scene }
        if (request.commonRules !== undefined && request.commonRules !== config.system_prompt) {
          config.system_prompt = request.commonRules
          config.prompt_template_id = null
          config.prompt_template_version = null
          config.user_prompt_template = null
        }
        config.scene_common_rules = config.system_prompt || ''
        await api.put(`/sessions/${request.sessionId}/config`, config)
        if (request.version !== sceneChangeVersion) continue
        const session = sessions.value.find(item => item.id === request.sessionId)
        if (session) session.session_config = config
        if (currentSessionId.value !== request.sessionId) continue
        await loadSessionMessages(request.sessionId)
        if (request.version !== sceneChangeVersion) continue
        const question = [...messages.value].reverse().find(item => item.role === 'user' && item.id)
        if (request.rerun && question) {
          // Start without waiting: another click can immediately abort this stream.
          void handleRegenerateMessage({ messageId: question.id, newContent: question.content, preserveAnswer: true })
        }
      } catch (error) {
        if (request.version === sceneChangeVersion) showNotification('切换场景失败：' + (error.response?.data?.detail || error.message), 'error')
      } finally { request.onSettled?.() }
    }
  } finally { sceneSwitching.value = false }
}

const DEFAULT_SCREENSHOT_PROMPT = '请识别截图中的笔试题。回答时请在开头先简要、直接地给出最终答案，然后再逐题说明简要思路；代码题请给出可运行代码并分析时间复杂度和空间复杂度。'

function normalizeStreamTargets(data) {
  if (Array.isArray(data.targets) && data.targets.length > 0) return data.targets
  return (data.models || []).map(model => ({
    key: model,
    model,
    source_name: model.includes('/') ? model.split('/')[0] : 'unknown'
  }))
}

function logProviderRequest(data) {
  const request = data.request || {}
  const model = request.parameters?.model || data.model_key || '未知模型'
  const stage = data.stage === 'regenerate' ? '重新生成' : '发送消息'
  console.groupCollapsed(`📤 ${stage} → ${request.provider || '供应商'} · ${model}`)
  const snapshot = JSON.parse(JSON.stringify(request))
  console.log('实际请求参数（密钥已隐藏，图片以 SHA-256 标识）:', snapshot)
  console.groupEnd()
}

// 状态
const messages = ref([])
const inputMessage = ref('')
const isSending = ref(false)
const isRecording = ref(false)
const selectedMicrophone = ref(null)
const selectedUsbInput = ref(null)
const recordingInputSource = ref('microphone')
const recordingDeviceRevision = ref(0)
const defaultRecordingDevice = ref(null)
const resolvedMicrophone = computed(() => selectedMicrophone.value || defaultRecordingDevice.value)
const resolvedSoundCard = computed(() => selectedUsbInput.value || defaultRecordingDevice.value)
const sameRecordingDevice = computed(() => resolvedMicrophone.value && resolvedSoundCard.value
  && resolvedMicrophone.value.index === resolvedSoundCard.value.index)
function storedRecordingMode(key, fallback) {
  try {
    const mode = userStorage.getItem(key)
    return RECORDING_MODES.includes(mode) ? mode : fallback
  } catch { return fallback }
}
const buttonRecordingMode = ref(storedRecordingMode('recordingButtonMode', 'mix'))
const rightClickRecordingMode = ref(storedRecordingMode('recordingRightClickMode', 'usb'))
const activeRecordingMode = ref('mix')
const recordingModeLabel = computed(() => recordingModeName(isRecording.value
  ? activeRecordingMode.value : buttonRecordingMode.value, sameRecordingDevice.value))
function saveRecordingModes() {
  try {
    userStorage.setItem('recordingButtonMode', buttonRecordingMode.value)
    userStorage.setItem('recordingRightClickMode', rightClickRecordingMode.value)
  } catch {}
}
function routeForRecording(source) {
  return recordingRoute(source, source === 'usb' ? rightClickRecordingMode.value : buttonRecordingMode.value,
    selectedMicrophone.value, selectedUsbInput.value)
}
const recordingDeviceSummary = computed(() => `麦克风：${resolvedMicrophone.value?.name || '系统默认'} ＋ 声卡：${resolvedSoundCard.value?.name || '系统默认'}`)
async function resetRecordingInputs() {
  if (isRecording.value || isProcessingRecording.value) return
  try {
    userStorage.removeItem('recordingMicrophone')
    userStorage.removeItem('recordingUsbInput')
  } catch {}
  await initializeRecordingInputs()
  recordingDeviceRevision.value++
}

let recordingDraftPrefix = ''
let latestRecordingTranscript = ''
let clearedTranscriptLength = 0

function recordingComposerText(text) {
  latestRecordingTranscript = text || ''
  return [recordingDraftPrefix, latestRecordingTranscript.slice(clearedTranscriptLength)].filter(Boolean).join('\n')
}

function clearComposerOnly() {
  inputMessage.value = ''
  recordingDraftPrefix = ''
  clearedTranscriptLength = latestRecordingTranscript.length
}
async function initializeRecordingInputs() {
  try {
    const { devices, default_index } = await api.get('/recording/devices')
    defaultRecordingDevice.value = devices.find(device => device.index === default_index) || null
    const saved = key => { try { return JSON.parse(userStorage.getItem(key) || 'null') } catch { return null } }
    selectedMicrophone.value = preferredRecordingDevice(devices, saved('recordingMicrophone'), 'microphone')
    selectedUsbInput.value = preferredRecordingDevice(devices, saved('recordingUsbInput'), 'usb')
  } catch (error) { console.warn('读取录音设备失败:', error) }
}
onMounted(initializeRecordingInputs)

const isTyping = ref(false)
function loadLayoutPreferences() {
  try { return JSON.parse(userStorage.getItem('chatLayoutPreferences') || '{}') } catch { return {} }
}
const layoutPreferences = loadLayoutPreferences()
const headerPosition = ref(layoutPreferences.header === 'bottom' ? 'bottom' : 'top')
const scenePosition = ref(layoutPreferences.scenes === 'bottom' ? 'bottom' : 'top')
const composerOpacity = ref(Number.isFinite(layoutPreferences.opacity) ? layoutPreferences.opacity : 25)
const composerHeight = ref(80), inputAreaRef = ref(null), captureButtonRef = ref(null)
let composerObserver
watch([headerPosition, scenePosition], async () => { await nextTick(); captureButtonRef.value?.reposition() })
watch([headerPosition, scenePosition, composerOpacity], () => userStorage.setItem('chatLayoutPreferences', JSON.stringify({ header: headerPosition.value, scenes: scenePosition.value, opacity: composerOpacity.value })))
onMounted(() => {
  composerObserver = new ResizeObserver(() => {
    composerHeight.value = inputAreaRef.value?.$el?.getBoundingClientRect().height || 80
  })
  if (inputAreaRef.value?.$el) composerObserver.observe(inputAreaRef.value.$el)
})
onUnmounted(() => composerObserver?.disconnect())
const showSettings = ref(false)
const showSessionSettings = ref(false)
const settingsPanelWidth = ref(370)
const messageListRef = ref(null)
const recordingAudioLevel = ref(0)
watch(isRecording, value => { if (!value) recordingAudioLevel.value = 0 })
const abortController = ref(null) // 用于取消请求
const captureConnected = ref(false)
const captureSourceName = ref('')
const captureSourceType = ref('camera')
const cameraDevices = ref([])
const selectedCameraId = ref(userStorage.getItem('captureCameraId') || '')
const isCapturing = ref(false)
const stoppingResponses = ref(false)
const doubaoBusy = ref(false)
const responseBusy = computed(() => Boolean(abortController.value) || isSending.value
  || doubaoBusy.value || activeCaptureCount.value > 0 || isCapturing.value || restartingResponse.value || stoppingResponses.value)
const captureMode = ref('immediate')
const pendingCaptures = ref([])
const captureQueue = ref([])
const activeCaptureCount = ref(0)
const pendingCaptureCount = computed(() => pendingCaptures.value.length + captureQueue.value.length)
const pendingCapturePreviews = computed(() => {
  const attachments = [...pendingCaptures.value, ...captureQueue.value.map(item => item.attachment)]
  return attachments.map(item => ({
    id: item.id,
    url: privateUrl(`/api/attachments/${encodeURIComponent(currentSessionId.value || '')}/${encodeURIComponent(item.id)}`)
  }))
})
let captureVersion = 0
let drainingCaptures = false
let displayCapture = null
let captureUploadController = null

// 会话管理状态
const sessions = ref([])
const currentSessionId = ref(null)
let displayedSessionId = null

const currentSession = computed(() => {
  return sessions.value.find(s => s.id === currentSessionId.value) || null
})

const messageDisplaySettings = computed(() => ({
  fontSize: currentSession.value?.session_config?.display_font_size ?? 16,
  lineHeight: currentSession.value?.session_config?.display_line_height ?? 1.7
}))

// 配置（从后端 config.py 读取）
const config = ref({
  sources: [],
  current_source: '',
  current_model: ''
})

// 从后端加载配置（读取 config.py）
async function loadConfig() {
  try {
    const data = await api.get('/config')
    config.value = data
    console.log('从 config.py 加载配置:', data)
    console.log(`当前使用: ${data.current_source} - ${data.current_model}`)
  } catch (error) {
    console.error('加载配置失败:', error)
  }
}

// 刷新配置
async function handleRefreshConfig() {
  await loadConfig()
  showSettings.value = false
  showNotification(`当前配置: ${config.value.current_source} - ${config.value.current_model}`, 'success')
}

async function handleSessionConfigUpdated() {
  // 重新加载当前会话的完整数据（包括 session_config）
  if (currentSessionId.value) {
    try {
      const sessionData = await api.get(`/sessions/${currentSessionId.value}`)
      // 更新 sessions 数组中的当前会话对象
      const index = sessions.value.findIndex(s => s.id === currentSessionId.value)
      if (index !== -1) {
        // 保留索引的基本字段，更新完整数据
        sessions.value[index] = {
          ...sessions.value[index],
          ...sessionData
        }
      }
      console.log('会话配置已更新:', sessionData.session_config)
    } catch (error) {
      console.error('重新加载会话失败:', error)
    }
  }
  showNotification('会话配置已更新', 'success')
  showSessionSettings.value = false
}

// 保存配置（向后兼容）
async function handleSaveConfig(newConfig) {
  try {
    await api.post('/config', newConfig)
    await loadConfig()
    showSettings.value = false
    showNotification('配置已保存', 'success')
  } catch (error) {
    showNotification('保存失败: ' + error.message, 'error')
  }
}

// 打断当前回答
function stopCurrentResponse() {
  const controller = abortController.value
  if (controller) controller.abort()
  return controller?.finished || Promise.resolve()
}

// Explicit stop covers every active stream, including parallel camera requests.
async function stopAllResponses() {
  if (stoppingResponses.value) return
  stoppingResponses.value = true
  ++restartVersion
  restartingResponse.value = false
  stopCaptureSource()
  doubaoOverlay.value?.cancel()
  // Prevent queued photos from starting as cancelled streams finish.
  const queued = captureQueue.value.splice(0)
  for (const item of queued) releaseUnusedCapture(item.sessionId, item.attachment.id)
  try {
    await interruptAnswerStreams(abortController.value, captureControllers, 'user-stop')
    showNotification('已停止生成，保留已显示的内容', 'info')
  } finally {
    stoppingResponses.value = false
  }
}

// 发送消息
async function handleSendMessage(options = {}) {
  if (stoppingResponses.value) return
  if (restartingResponse.value) return showNotification('正在应用修改，请稍候', 'info')
  if (sceneSwitching.value) return showNotification('正在切换场景，请稍候', 'warning')
  const attachments = Array.isArray(options?.attachments) ? options.attachments : []
  const fallbackMessage = options?.fallbackMessage || ''
  const messageOverride = options?.messageOverride || ''
  // 如果正在发送
  if (isSending.value) {
    // 如果输入框有新内容，先打断再发送新消息
    if (inputMessage.value.trim()) {
      const newMessage = inputMessage.value.trim()
      await stopCurrentResponse()
      inputMessage.value = newMessage
      // 递归调用发送新消息
      return handleSendMessage(options)
    } else {
      // 输入框为空，只是打断
      stopCurrentResponse()
      return
    }
  }
  
  if (!inputMessage.value.trim() && !messageOverride && attachments.length === 0) return
  
  const message = messageOverride || inputMessage.value.trim() || fallbackMessage
  if (!message) return
  if (!messageOverride) inputMessage.value = ''
  
  // 添加用户消息
  const requestId = `text-${Date.now()}-${Math.random().toString(36).slice(2)}`
  messages.value.push({
    local_request_id: requestId,
    role: 'user',
    content: message,
    attachments,
    time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  })
  
  // 先添加一个空的 assistant 消息（单模型情况下使用）
  messages.value.push({
    role: 'assistant',
    content: '',
    time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    is_typing_dots: true // 显示打字机动画
  })

  isTyping.value = true
  isSending.value = true
  
  // 创建新的 AbortController
  const sendController = streamController()
  abortController.value = sendController
  
  // 多模型响应容器（后端会告诉我们有多少个模型）
  let modelMessages = []  // 存储多个模型的消息对象
  let refreshPromise = null
  
  console.log('🚀 开始发送消息，等待流式响应...')
  const startTime = Date.now()
  let chunkCount = 0
  let lastChunkTime = startTime
  
  try {
    const response = await authFetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        message,
        session_id: currentSessionId.value,
        attachment_ids: attachments.map(attachment => attachment.id)
      }),
      signal: sendController.signal
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    if (showDoubao.value && !options.skipDoubao && attachments.length === 0) {
      doubaoOverlay.value?.submit({ session_id: currentSessionId.value, text: message })
    }
    bindStreamingQuestion(messages.value, requestId, response)
    console.log('✅ 连接成功，开始接收流式数据...')
    
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    
    while (true) {
      const { done, value } = await reader.read()
      
      if (done) {
        if (buffer.trim()) {
          processLine(buffer)
        }
        console.log(`✅ 流式接收完成！总耗时: ${((Date.now() - startTime) / 1000).toFixed(2)}秒`)
        break
      }
      
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      
      for (const line of lines) {
        processLine(line)
      }
    }
    if (refreshPromise) await refreshPromise
    
    function processLine(line) {
      if (sendController.signal.aborted) return
      const trimmedLine = line.trim()
      if (!trimmedLine || !trimmedLine.startsWith('data: ')) return
      
      try {
        const jsonStr = trimmedLine.slice(6)
        const data = JSON.parse(jsonStr)
        
        if (data.type === 'provider_request') {
          logProviderRequest(data)
        } else if (data.type === 'multi_model_start') {
          // 多模型模式开始
          console.log('🎯 多模型模式:', data.models)
          
          // 移除之前添加的单个空消息
          for (let i = messages.value.length - 1; i >= 0; i--) {
            if (messages.value[i].role === 'assistant' && messages.value[i].content === '') {
              messages.value.splice(i, 1)
              break
            }
          }
          
          // 创建一个多模型容器消息
          const multiModelMsg = {
            role: 'assistant',
            is_multi_model: true,
            models: [],
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            is_typing_dots: true // 显示打字机动画
          }
          
          // 为每个模型创建子消息对象
          normalizeStreamTargets(data).forEach((target, index) => {
            const msgObj = {
              content: '',
              model_info: {
                id: target.key,
                name: target.model,
                provider: target.source_name
              },
              model_index: index,
              model: target.model,
              model_key: target.key,
              source_name: target.source_name
            }
            multiModelMsg.models.push(msgObj)
            modelMessages.push(msgObj)
          })
          
          messages.value.push(multiModelMsg)
          isTyping.value = false
          
        } else if (data.type === 'model_start') {
          // 某个模型开始响应
          console.log(`🤖 模型 ${data.model} 开始响应`)
          
        } else if (data.type === 'content' || data.type === 'reasoning') {
          chunkCount++
          const now = Date.now()
          lastChunkTime = now
          
          if (data.model_index !== undefined && modelMessages.length > 0) {
            // 多模型模式：更新对应索引的消息
            if (modelMessages[data.model_index]) {
              // 直接更新 messages.value 中的多模型消息，触发 Vue 响应式更新
              const multiModelMsg = messages.value[messages.value.length - 1]
              if (multiModelMsg && multiModelMsg.is_multi_model && multiModelMsg.models[data.model_index]) {
                appendAnswerDelta(multiModelMsg.models[data.model_index], data)
              }
            }
          } else {
            // 单模型模式：找到最后一条 assistant 消息
            for (let i = messages.value.length - 1; i >= 0; i--) {
              if (messages.value[i].role === 'assistant') {
                appendAnswerDelta(messages.value[i], data)
                break
              }
            }
          }
          isTyping.value = false
          
        } else if (data.type === 'model_done') {
          console.log(`✅ 模型 ${data.model} 完成`)
          
        } else if (data.type === 'model_error') {
          console.error('❌ 模型错误:', data.model, data.message)
          const modelLabel = data.source_name ? `${data.source_name} · ${data.model}` : data.model
          showNotification(`模型 ${modelLabel} 错误: ${data.message}`, 'error')
          
        } else if (data.type === 'error') {
          console.error('❌ 收到错误:', data.message)
          showNotification('错误: ' + data.message, 'error')
          
        } else if (data.type === 'done') {
          isTyping.value = false
          modelMessages = []  // 清空多模型缓存
          // 重新加载消息以获取完整的带ID的数据
          if (currentSessionId.value) {
            refreshPromise = loadSessionMessages(currentSessionId.value).then(() => {
              return loadSessions()
            }).catch(err => {
              console.error('重新加载消息失败:', err)
            })
          }
        }
      } catch (e) {
        console.error('❌ 解析 SSE 数据失败:', line, e)
      }
    }
  } catch (error) {
    // 如果是用户主动取消
    if (sendController.signal.aborted || error.name === 'AbortError') {
      console.log('✋ 请求已被用户取消')
      if (sendController.signal.reason !== 'scene-switch') showNotification('已停止生成', 'info')
      
      // 保留已生成的内容，只移除空消息
      if (modelMessages.length > 0) {
        // 多模型：检查是否有内容
        const lastMsg = messages.value[messages.value.length - 1]
        if (lastMsg && lastMsg.is_multi_model) {
          // 检查是否所有模型都没有内容
          const hasContent = lastMsg.models.some(m => m.content && m.content.trim())
          if (!hasContent) {
            // 所有模型都没有内容，移除整个消息
            messages.value.splice(messages.value.length - 1, 1)
          } else {
            // 有内容，保留消息，移除打字动画标记
            lastMsg.is_typing_dots = false
          }
        }
      } else {
        // 单模型：检查最后一条 assistant 消息是否有内容
        for (let i = messages.value.length - 1; i >= 0; i--) {
          if (messages.value[i].role === 'assistant') {
            if (!messages.value[i].content || !messages.value[i].content.trim()) {
              // 没有内容，移除
              messages.value.splice(i, 1)
            } else {
              // 有内容，保留，移除打字动画标记
              messages.value[i].is_typing_dots = false
            }
            break
          }
        }
      }
    } else {
      // 真正的错误，移除所有临时消息
      console.error('发送消息失败:', error)
      showNotification('发送失败: ' + error.message, 'error')
      
      // 移除临时添加的 assistant 消息
      if (modelMessages.length > 0) {
        // 多模型：移除所有模型的消息
        modelMessages.forEach(() => {
          for (let i = messages.value.length - 1; i >= 0; i--) {
            if (messages.value[i].role === 'assistant') {
              messages.value.splice(i, 1)
              break
            }
          }
        })
      } else {
        // 单模型：移除最后一条 assistant 消息
        for (let i = messages.value.length - 1; i >= 0; i--) {
          if (messages.value[i].role === 'assistant') {
            messages.value.splice(i, 1)
            break
          }
        }
      }
    }
  } finally {
    isSending.value = false
    isTyping.value = false
    if (refreshPromise) await refreshPromise
    if (abortController.value === sendController) abortController.value = null
    sendController.finish()
    modelMessages = []
    if (captureQueue.value.length && !drainingCaptures) queueMicrotask(drainCaptureQueue)
  }
}

function screenshotQuestion(extra = '') {
  const prompt = currentSession.value?.session_config?.screenshot_prompt?.trim() || DEFAULT_SCREENSHOT_PROMPT
  return extra ? `${prompt}\n\n用户补充要求：${extra}` : prompt
}

function toggleCaptureMode() {
  captureMode.value = captureMode.value === 'immediate' ? 'collect' : 'immediate'
  showNotification(captureMode.value === 'collect' ? '截图将累积，点击发送后一起提问' : '每张截图单独提问', 'info')
}

function clearPendingCaptures() {
  pasteImageVersion++
  const sessionId = currentSessionId.value
  for (const item of pendingCaptures.value) releaseUnusedCapture(sessionId, item.id)
  for (const item of captureQueue.value) releaseUnusedCapture(sessionId, item.attachment.id)
  pendingCaptures.value = []
  captureQueue.value = []
}

function removePendingCapture(id) {
  if (pendingCaptures.value.some(item => item.id === id) || captureQueue.value.some(item => item.attachment.id === id)) {
    releaseUnusedCapture(currentSessionId.value, id)
  }
  pendingCaptures.value = pendingCaptures.value.filter(item => item.id !== id)
  captureQueue.value = captureQueue.value.filter(item => item.attachment.id !== id)
}

function releaseUnusedCapture(sessionId, id) {
  if (!sessionId || !id) return
  authFetch(privateUrl(`/api/attachments/${encodeURIComponent(sessionId)}/${encodeURIComponent(id)}`), {
    method: 'DELETE'
  }).catch(error => console.warn('清理未使用截图失败:', error))
}

function cancelCapture() {
  stopCaptureSource()
  clearPendingCaptures()
  showNotification('已取消拍照并断开画面来源', 'info')
}

function handleComposerSend() {
  if (pasteImageUploads.value > 0) return ElMessage.warning('图片上传中，请稍候')
  if (sceneSwitching.value) return showNotification('正在切换场景，请稍候', 'warning')
  if (activeCaptureCount.value > 0) {
    showNotification('截图正在并行回答，完成后可发送文字', 'info')
    return
  }
  if (isSending.value) return handleSendMessage()
  if (!pendingCaptures.value.length) return handleSendMessage()
  const attachments = pendingCaptures.value.splice(0)
  const extra = inputMessage.value.trim()
  inputMessage.value = ''
  return handleSendMessage({ attachments, messageOverride: screenshotQuestion(extra) })
}

async function sendImmediateCapture(item) {
  const requestId = `capture-${Date.now()}-${Math.random().toString(36).slice(2)}`
  const userMessage = {
    role: 'user', content: item.message, attachments: [item.attachment],
    local_request_id: requestId,
    time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }
  const assistantMessage = {
    role: 'assistant', content: '', is_typing_dots: true,
    local_request_id: requestId,
    time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }
  messages.value.push(userMessage, assistantMessage)
  const controller = streamController()
  captureControllers.add(controller)
  activeCaptureCount.value++
  let completed = false
  try {
    const response = await authFetch('/api/chat', {
      method: 'POST',
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: item.message,
        session_id: item.sessionId,
        attachment_ids: [item.attachment.id]
      })
    })
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw new Error(data.detail || `HTTP ${response.status}`)
    }
    bindStreamingQuestion(messages.value, requestId, response)
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    const processLine = line => {
      if (controller.signal.aborted) return
      if (!line.startsWith('data: ')) return
      let data
      try { data = JSON.parse(line.slice(6)) } catch { return }
      if (data.type === 'provider_request') {
        logProviderRequest(data)
      } else if (data.type === 'multi_model_start') {
        const index = messages.value.findIndex(message => message.local_request_id === requestId && message.role === 'assistant')
        if (index < 0) return
        messages.value[index] = {
          role: 'assistant', is_multi_model: true, is_typing_dots: true,
          local_request_id: requestId,
          models: normalizeStreamTargets(data).map((target, modelIndex) => ({
            content: '', model_index: modelIndex, model: target.model,
            model_key: target.key, source_name: target.source_name,
            model_info: { id: target.key, name: target.model, provider: target.source_name }
          }))
        }
      } else if (data.type === 'content') {
        const message = messages.value.find(candidate => candidate.local_request_id === requestId && candidate.role === 'assistant')
        if (!message) return
        if (data.model_index !== undefined && message.models?.[data.model_index]) {
          message.models[data.model_index].content += data.data
        } else if (data.model_index === undefined) {
          message.content += data.data
        }
      } else if (data.type === 'model_error' || data.type === 'error') {
        showNotification(data.message || '截图回答失败', 'error')
      } else if (data.type === 'done') {
        completed = true
      }
    }
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) processLine(line.trim())
    }
    if (buffer.trim()) processLine(buffer.trim())
    if (!completed && !controller.signal.aborted) showNotification('截图回答未完成，请检查模型请求', 'warning')
  } catch (error) {
    if (!controller.signal.aborted) {
      console.error('截图发送失败:', error)
      showNotification(`截图发送失败: ${error.message}`, 'error')
    }
  } finally {
    const message = messages.value.find(candidate => candidate.local_request_id === requestId && candidate.role === 'assistant')
    if (message) message.is_typing_dots = false
    if (!completed) releaseUnusedCapture(item.sessionId, item.attachment.id)
    activeCaptureCount.value--
    if (!['scene-switch', 'user-stop'].includes(controller.signal.reason) && activeCaptureCount.value === 0 && currentSessionId.value && !isSending.value) {
      try {
        await loadSessionMessages(currentSessionId.value)
        await loadSessions()
      } catch (error) {
        console.warn('刷新截图回答失败:', error)
      }
    }
    captureControllers.delete(controller)
    controller.finish()
  }
}

async function drainCaptureQueue() {
  if (drainingCaptures || isSending.value || sceneSwitching.value || restartingResponse.value || stoppingResponses.value) return
  drainingCaptures = true
  try {
    while (captureQueue.value.length) {
      const item = captureQueue.value.shift()
      if (item.sessionId !== currentSessionId.value) {
        releaseUnusedCapture(item.sessionId, item.attachment.id)
        continue
      }
      void sendImmediateCapture(item)
    }
  } finally {
    drainingCaptures = false
  }
}

function stopCaptureSource() {
  captureVersion++
  captureUploadController?.abort()
  captureUploadController = null
  isCapturing.value = false
  displayCapture?.stop()
  displayCapture = null
  captureConnected.value = false
  captureSourceName.value = ''
}

function changeCaptureSource(type) {
  stopCaptureSource()
  captureSourceType.value = type
}

function changeCamera(id) {
  stopCaptureSource()
  selectedCameraId.value = id
  userStorage.setItem('captureCameraId', id)
}

async function refreshCameraDevices() {
  try {
    const devices = await navigator.mediaDevices?.enumerateDevices()
    cameraDevices.value = (devices || []).filter(device => device.kind === 'videoinput' && device.deviceId)
  } catch (error) { console.warn('读取摄像头列表失败:', error) }
}
onMounted(() => {
  void refreshCameraDevices()
  navigator.mediaDevices?.addEventListener('devicechange', refreshCameraDevices)
})
onUnmounted(() => navigator.mediaDevices?.removeEventListener('devicechange', refreshCameraDevices))

function ensureDisplayCapture() {
  if (!displayCapture) {
    const Capture = captureSourceType.value === 'camera' ? CameraCapture : DisplayScreenCapture
    const capture = new Capture(() => {
      if (displayCapture !== capture) return
      captureConnected.value = false
      captureSourceName.value = ''
      showNotification('画面来源已断开', 'info')
    }, devices => { if (displayCapture === capture) cameraDevices.value = devices })
    displayCapture = capture
  }
  return displayCapture
}

async function selectCaptureSource() {
  const capture = ensureDisplayCapture()
  const version = captureVersion
  const label = await capture.selectSource(selectedCameraId.value)
  if (version !== captureVersion || displayCapture !== capture) {
    capture.stop()
    throw new DOMException('拍照已停止', 'AbortError')
  }
  captureConnected.value = true
  captureSourceName.value = label
}

async function uploadScreenshot(frame, sessionId = currentSessionId.value, signal) {
  if (!sessionId) {
    throw new Error('当前没有可用会话')
  }
  const formData = new FormData()
  formData.append('session_id', sessionId)
  formData.append('width', String(frame.width))
  formData.append('height', String(frame.height))
  formData.append('screenshot', frame.blob, `capture-${Date.now()}.webp`)
  const response = await authFetch('/api/attachments/screenshots', {
    method: 'POST',
    signal,
    body: formData
  })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    if (response.status === 405) {
      throw new Error('截图接口尚未加载，请重启后端服务后重试')
    }
    throw new Error(data.detail || `截图上传失败 (${response.status})`)
  }
  return response.json()
}

async function handleCaptureAndSend() {
  if (stoppingResponses.value) return
  if (sceneSwitching.value) return showNotification('正在切换场景，请稍候', 'warning')
  if (isCapturing.value) return

  isCapturing.value = true
  const version = ++captureVersion
  const uploadController = new AbortController()
  captureUploadController = uploadController
  const captureSessionId = currentSessionId.value
  try {
    const capture = ensureDisplayCapture()
    if (!capture.connected) {
      await selectCaptureSource()
    }
    if (version !== captureVersion) { capture.stop(); return }
    const frame = await capture.capture()
    if (version !== captureVersion) { capture.stop(); return }
    try {
      await copyImageBlob(frame.clipboardBlob)
    } catch (clipboardError) {
      // Clipboard permission/support must not prevent the screenshot question.
      console.warn('截图已生成，但复制到剪贴板失败:', clipboardError)
      showNotification('截图已生成，但浏览器未允许写入图片剪贴板', 'warning', 3500)
    }
    const attachment = await uploadScreenshot(frame, captureSessionId, uploadController.signal)
    if (version !== captureVersion || captureSessionId !== currentSessionId.value) {
      releaseUnusedCapture(captureSessionId, attachment.id)
      capture.stop()
      return
    }
    captureConnected.value = true
    captureSourceName.value = capture.label
    if (captureMode.value === 'collect') {
      pendingCaptures.value.push(attachment)
      showNotification(`已累积 ${pendingCaptures.value.length} 张截图`, 'success')
    } else {
      const extraRequirement = inputMessage.value.trim()
      inputMessage.value = ''
      captureQueue.value.push({
        attachment,
        message: screenshotQuestion(extraRequirement),
        sessionId: captureSessionId
      })
      void drainCaptureQueue()
      showNotification(captureSourceType.value === 'camera' ? '拍照成功，已提交回答' : '截图成功，已提交回答', 'success')
    }
  } catch (error) {
    if (version !== captureVersion || error?.name === 'AbortError') return
    if (error?.name === 'NotAllowedError') {
      showNotification(captureSourceType.value === 'camera' ? '未获得摄像头权限，请在浏览器中允许使用摄像头' : '未获得窗口或标签页共享权限', 'warning')
    } else {
      console.error('截图答题失败:', error)
      showNotification(error.message || '截图答题失败', 'error', 5000)
    }
    captureConnected.value = Boolean(displayCapture?.connected)
    if (!captureConnected.value) captureSourceName.value = ''
  } finally {
    if (version === captureVersion) isCapturing.value = false
    if (captureUploadController === uploadController) captureUploadController = null
  }
}

async function handleCaptureForEdit() {
  if (isCapturing.value || stoppingResponses.value) return
  isCapturing.value = true
  const version = ++captureVersion
  const uploadController = new AbortController()
  captureUploadController = uploadController
  const sessionId = currentSessionId.value
  try {
    const capture = ensureDisplayCapture()
    if (!capture.connected) await selectCaptureSource()
    if (version !== captureVersion) { capture.stop(); return }
    const frame = await capture.capture()
    if (version !== captureVersion) { capture.stop(); return }
    const attachment = await uploadScreenshot(frame, sessionId, uploadController.signal)
    if (version !== captureVersion || !messageListRef.value?.addCapturedEditingImage(attachment, sessionId)) {
      releaseUnusedCapture(sessionId, attachment.id)
    }
  } catch (error) {
    if (version !== captureVersion || error?.name === 'AbortError') return
    if (error?.name !== 'NotAllowedError') showNotification(error.message || '拍照添加失败', 'error')
  } finally {
    if (version === captureVersion) isCapturing.value = false
    if (captureUploadController === uploadController) captureUploadController = null
  }
}

async function handleResetCapture() {
  if (isCapturing.value || stoppingResponses.value) return
  ensureDisplayCapture().stop()
  captureConnected.value = false
  captureSourceName.value = ''
  isCapturing.value = true
  const version = ++captureVersion
  try {
    await selectCaptureSource()
    if (captureSourceType.value === 'camera') showNotification(`已连接摄像头：${captureSourceName.value}，点击「立即拍照」取图`, 'info')
  } catch (error) {
    if (version !== captureVersion || error?.name === 'AbortError') return
    showNotification(error?.name === 'NotAllowedError' ? '请在浏览器中允许访问所选画面来源' : (error.message || '连接画面来源失败'), 'error')
  } finally {
    if (version === captureVersion) isCapturing.value = false
  }
  // Selecting a window is an explicit screenshot action, not just a connection.
  if (captureSourceType.value === 'screen' && version === captureVersion && captureConnected.value) {
    await handleCaptureAndSend()
  }
}

// 语音录音防抖标志
const isProcessingRecording = ref(false)
const recordingPhase = ref('idle')
let removeMicrophoneContextMenu
onMounted(() => { removeMicrophoneContextMenu = installMicrophoneContextMenu(window, () => handleToggleRecording('usb'), {
  getAction: () => currentSession.value?.session_config?.right_click_action || 'record',
  capturePhoto: handleCaptureAndSend
}) })
onUnmounted(() => removeMicrophoneContextMenu?.())
// 记录开始录音时的会话ID，确保停止时发送到正确的会话
let recordingSessionId = null
// 录音状态轮询定时器
let recordingStatusInterval = null
let recordingStatusPending = false
let recordingRevision = 0
let captureWarningShown = false

// 检查录音状态（轮询）
async function checkRecordingStatus() {
  if (recordingStatusPending || !isRecording.value || recordingPhase.value !== 'idle') return
  const revision = recordingRevision
  recordingStatusPending = true
  try {
    const status = await api.get('/recording/status')
    if (!isRecording.value || revision !== recordingRevision || recordingPhase.value !== 'idle') return
    recordingAudioLevel.value = status.audio_level || 0
    if (status.capture_warning && !captureWarningShown) {
      captureWarningShown = true
      showNotification(status.capture_warning, 'warning', 6000)
    }
    if (status.error) {
      await handleStopRecording({ sendMessage: false })
      showNotification(status.error, 'error', 6000)
      return
    }

    // Soniox returns interim hypotheses during the stream. Reflect the latest
    // hypothesis in the composer while recording; the stop endpoint still
    // supplies the authoritative final text.
    if (isRecording.value && status.partial_text) {
      inputMessage.value = recordingComposerText(status.partial_text)
    }
    
    // 如果后端显示已自动停止，但前端还显示在录音
    if (status.auto_stopped && isRecording.value) {
      console.log('⏰ [自动停止检测] 后端录音已自动停止，获取识别结果')
      
      // 停止轮询
      if (recordingStatusInterval) {
        clearInterval(recordingStatusInterval)
        recordingStatusInterval = null
      }
      
      // 直接调用停止录音获取结果（不改变 isRecording.value，由 handleStopRecording 处理）
      showNotification('录音已达到时长上限，正在识别...', 'warning')
      await handleStopRecording({ sendMessage: false })
    }
    
    // 如果后端不在录音但前端显示在录音（异常情况）
    if (!status.is_recording && isRecording.value && !status.auto_stopped) {
      console.warn('⚠️ [状态不同步] 后端未录音但前端显示录音中，修正状态')
      isRecording.value = false
      if (recordingStatusInterval) {
        clearInterval(recordingStatusInterval)
        recordingStatusInterval = null
      }
    }
  } catch (error) {
    recordingAudioLevel.value = 0
    console.error('检查录音状态失败:', error)
  } finally {
    recordingStatusPending = false
  }
}

// 停止录音并获取结果（独立函数，供自动停止和手动停止调用）
async function handleStopRecording({ sendMessage = true, silent = false } = {}) {
  escapeGesture.reset()
  recordingRevision++
  recordingPhase.value = sendMessage ? 'stopping' : 'cancelling'
  const stopClickTime = Date.now()
  console.log(`🔴 [停止录音:${new Date(Date.now()).toLocaleTimeString()}.${Date.now() % 1000}] 停止录音: ${new Date(stopClickTime).toLocaleTimeString()}.${stopClickTime % 1000}`)
  
  isRecording.value = false
  if (sendMessage) showNotification('正在完成识别...', 'info')
  
  // 停止状态轮询
  if (recordingStatusInterval) {
    clearInterval(recordingStatusInterval)
    recordingStatusInterval = null
  }
  
  // 保存当前录音会话ID（在 finally 之前保存，因为后面是异步操作）
  const targetSessionId = recordingSessionId
  const submitToDoubao = recordingWithDoubao
  recordingWithDoubao = false
  recordingSessionId = null  // 立即清除，允许新的录音
  
  try {
    console.log(`📡 [发送请求:${new Date(Date.now()).toLocaleTimeString()}.${Date.now() % 1000}] 向后端发送 /recording/stop 请求...`)
    const apiStartTime = Date.now()
    
    const data = await api.post(sendMessage ? '/recording/stop' : '/recording/stop?finalize=false', null,
      { timeout: sendMessage ? 60000 : 10000 })
    void loadSessions()
    
    const apiEndTime = Date.now()
    const apiDuration = apiEndTime - apiStartTime
    console.log(`✅ [收到响应:${new Date(apiEndTime).toLocaleTimeString()}.${apiEndTime % 1000}] API 请求耗时: ${apiDuration}ms`)
    console.log(`📝 [响应数据:${new Date(Date.now()).toLocaleTimeString()}.${Date.now() % 1000}] success=${data.success}, text="${data.text || ''}"${data.message ? ', message="' + data.message + '"' : ''}`)
    
    if (data.success && data.text) {
      const totalDuration = apiEndTime - stopClickTime
      console.log(`✅ [识别成功:${new Date(Date.now()).toLocaleTimeString()}.${Date.now() % 1000}] 总耗时: ${totalDuration}ms (从点击停止录音 到收到识别的响应结果)`)
      
      inputMessage.value = recordingComposerText(data.text)
      
      if (!sendMessage) {
        console.log('📝 [保留草稿] Esc 停止识别，结果保留在输入框且不发送')
        if (!silent) showNotification('识别已停止，文字已保留在输入框，可修改后再发送', 'success', 4000)
        return
      }

      // 如果录音时切换了会话，需要切换回原来的会话
      if (targetSessionId && targetSessionId !== currentSessionId.value) {
        console.log(`🔄 [会话切换] 录音期间会话已切换，发送到原始会话: ${targetSessionId}`)
        await handleSwitchSession(targetSessionId)
        // 切换会话会重新加载消息，但不会保留输入框草稿。
        inputMessage.value = recordingComposerText(data.text)
      }

      if (submitToDoubao) doubaoOverlay.value?.submit({ session_id: targetSessionId, audio_file: data.audio_file, text: inputMessage.value })

      console.log(`🚀 [发送消息:${new Date(Date.now()).toLocaleTimeString()}.${Date.now() % 1000}] 准备发送消息给模型...`)
      const sendStartTime = Date.now()
      
      // 不等待 handleSendMessage 完成，让它在后台运行
      // 这样用户可以在 AI 回答期间再次录音
      handleSendMessage({ skipDoubao: true }).then(() => {
        const sendEndTime = Date.now()
        const sendDuration = sendEndTime - sendStartTime
        console.log(`✅ [模型响应完成:${new Date(Date.now()).toLocaleTimeString()}.${Date.now() % 1000}] 模型响应耗时: ${sendDuration}ms`)
        
        const totalWithModel = sendEndTime - stopClickTime
        console.log(`🏁 [总耗时:${new Date(Date.now()).toLocaleTimeString()}.${Date.now() % 1000}] 从点击停止到模型响应完成: ${totalWithModel}ms`)
      }).catch(err => {
        console.error('发送消息失败:', err)
      })
    } else {
      // 显示详细的错误信息
      const errorMsg = data.message || '识别失败，请确保说话清晰'
      console.error(`❌ [识别失败:${new Date(Date.now()).toLocaleTimeString()}.${Date.now() % 1000}] ${errorMsg}`)
      showNotification(errorMsg, 'error', 5000)
    }
  } catch (error) {
    const errorMsg = error.response?.data?.message || error.message || '录音处理失败'
    console.error(`❌ [异常:${new Date(Date.now()).toLocaleTimeString()}.${Date.now() % 1000}] 录音处理失败:`, error)
    showNotification('录音处理失败: ' + errorMsg, 'error', 5000)
  } finally { recordingPhase.value = 'idle' }
}

// 开始录音
async function handleStartRecording(source = 'microphone') {
  escapeGesture.reset()
  recordingRevision++
  recordingPhase.value = 'starting'
  doubaoOverlay.value?.cancel()
  const startClickTime = Date.now()
  console.log(`🟢 [开始录音:${new Date(Date.now()).toLocaleTimeString()}.${Date.now() % 1000}] 点击开始按钮: ${new Date(startClickTime).toLocaleTimeString()}.${startClickTime % 1000}`)
  
  // 如果正在回答，先打断回答
  if (isSending.value) {
    console.log('🛑 [打断回答] 检测到正在回答，先停止当前回答')
    stopCurrentResponse()
  }
  
  try {
    console.log(`📡 [发送请求:${new Date(Date.now()).toLocaleTimeString()}.${Date.now() % 1000} ] 向后端发送 /recording/start 请求...`)
    const apiStartTime = Date.now()
    
    const route = routeForRecording(source)
    recordingDraftPrefix = inputMessage.value.trim()
    latestRecordingTranscript = ''
    clearedTranscriptLength = 0
    const response = await api.post('/recording/start', {
      ...route
    })
    
    const apiEndTime = Date.now()
    const apiDuration = apiEndTime - apiStartTime
    console.log(`✅ [录音已启动:${new Date(Date.now()).toLocaleTimeString()}.${Date.now() % 1000}] API 请求耗时: ${apiDuration}ms`)
    
    // ✅ 只有在后端成功启动后才设置前端状态
    if (response.success) {
      captureWarningShown = false
      recordingAudioLevel.value = 0
      isRecording.value = true
      recordingInputSource.value = source
      activeRecordingMode.value = source === 'usb' ? rightClickRecordingMode.value : buttonRecordingMode.value
      recordingWithDoubao = showDoubao.value
      recordingSessionId = currentSessionId.value  // 记录开始录音时的会话ID
      console.log(`📝 [记录会话] 录音开始于会话: ${recordingSessionId}`)
      showNotification('正在语音识别', 'info')
      
      // 以较短间隔同步 Soniox 的中间 token（停止接口仍返回最终文本）
      recordingStatusInterval = setInterval(checkRecordingStatus, 150)
    } else {
      console.error(`❌ [启动失败] 后端返回失败: ${response.message}`)
      showNotification('启动录音失败: ' + (response.message || '未知错误'), 'error')
    }
  } catch (error) {
    console.error(`❌ [异常:${new Date(Date.now()).toLocaleTimeString()}.${Date.now() % 1000}] 启动录音失败:`, error)
    showNotification('启动录音失败: ' + error.message, 'error')
  } finally { recordingPhase.value = 'idle' }
}

// 语音录音切换（供按钮和快捷键调用）
async function handleToggleRecording(source = (isRecording.value ? recordingInputSource.value : 'microphone')) {
  // 防止重复调用
  if (isProcessingRecording.value || recordingPhase.value !== 'idle') {
    console.warn('⚠️ [防抖] 正在处理录音请求，忽略重复调用')
    return
  }
  
  isProcessingRecording.value = true
  
  try {
    if (isRecording.value && recordingInputSource.value !== source) {
      recordingRevision++
      recordingPhase.value = 'switching'
      const route = routeForRecording(source)
      try {
        const response = await api.post('/recording/switch-input', route)
        if (!response.success) throw new Error(response.message || '切换输入设备失败')
      } catch (error) {
        if (error.response?.status !== 409) throw error
        // The old capture may have ended before this click (timeout/disconnect).
        // Finish preserving its draft, then honour the requested new source.
        await handleStopRecording({ sendMessage: false, silent: true })
        await handleStartRecording(source)
        return
      }
      recordingInputSource.value = source
      activeRecordingMode.value = source === 'usb' ? rightClickRecordingMode.value : buttonRecordingMode.value
      showNotification('已切换为' + recordingModeLabel.value + '，识别文字继续追加', 'info')
    } else if (isRecording.value) {
      // 停止录音
      await handleStopRecording({ sendMessage: true })
    } else {
      // 开始录音
      await handleStartRecording(source)
    }
  } catch (error) {
    showNotification(error.response?.data?.detail || error.message || '切换录音来源失败', 'error')
  } finally {
    recordingPhase.value = 'idle'
    isProcessingRecording.value = false
  }
}

// 清空对话
async function handleClearChat() {
  try {
    await ElMessageBox.confirm(
      '确定要清空当前对话吗？',
      '确认清空',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    // 用户取消
    return
  }
  
  try {
    await api.post('/chat/clear')
    messages.value = []
    showNotification('对话已清空', 'success')
  } catch (error) {
    showNotification('清空失败: ' + error.message, 'error')
  }
}

// ==================== 会话管理 ====================

// 加载会话列表
async function loadSessions({ selectCurrent = false, reloadMessages = false } = {}) {
  try {
    const selectedId = currentSessionId.value
    const data = await api.get('/sessions')
    const previous = new Map(sessions.value.map(session => [session.id, session]))
    // Index refreshes must retain the selected session's full configuration.
    sessions.value = (data.sessions || []).map(session => ({ ...previous.get(session.id), ...session }))
    const selectionUnchanged = currentSessionId.value === selectedId
    if (selectionUnchanged && (selectCurrent || !selectedId || !sessions.value.some(session => session.id === selectedId))) {
      currentSessionId.value = data.current_session_id || sessions.value[0]?.id || null
    }
    // Routine refreshes (recording stop, title/count updates) leave visible
    // answers intact, including the partial answer retained after cancellation.
    if (currentSessionId.value && (currentSessionId.value !== selectedId || reloadMessages)) {
      await loadSessionMessages(currentSessionId.value)
    }
  } catch (error) {
    console.error('加载会话列表失败:', error)
    showNotification('加载会话列表失败', 'error')
  }
}

// 加载指定会话的消息
async function loadSessionMessages(sessionId) {
  try {
    const data = await api.get(`/sessions/${sessionId}`)
    if (currentSessionId.value !== sessionId) return
    const sameVisibleSession = displayedSessionId === sessionId
    const readingPosition = sameVisibleSession ? messageListRef.value?.captureReadingPosition() : null
    messages.value = data.messages || []
    displayedSessionId = sessionId
    await nextTick()
    if (currentSessionId.value === sessionId && readingPosition) messageListRef.value?.restoreReadingPosition(readingPosition)
    // 同时更新 sessions 数组中的当前会话对象（包含完整的 session_config）
    const index = sessions.value.findIndex(s => s.id === sessionId)
    if (index !== -1) {
      sessions.value[index] = {
        ...sessions.value[index],
        ...data
      }
    }
    
    console.log('加载会话消息:', sessionId, messages.value.length, '条')
  } catch (error) {
    console.error('加载会话消息失败:', error)
  }
}

// 创建新会话
async function handleCreateSession() {
  try {
    const data = await api.post('/sessions', null, {
      params: { title: '新对话' }
    })
    
    if (data.success) {
      clearPendingCaptures()
      await loadSessions({ selectCurrent: true })
      showNotification('新会话已创建', 'success')
    }
  } catch (error) {
    console.error('创建会话失败:', error)
    showNotification('创建会话失败', 'error')
  }
}

// 切换会话
async function handleSwitchSession(sessionId) {
  if (sceneSwitching.value) return showNotification('正在切换场景，请稍候', 'warning')
  if (sessionId === currentSessionId.value) return
  if (pendingCaptureCount.value) showNotification('切换会话，未发送的截图已清空', 'info')
  clearPendingCaptures()
  
  // 如果正在录音，先停止录音（除非是录音停止后自动切换回原会话）
  if (isRecording.value) {
    console.log('⚠️ [会话切换] 检测到会话切换，停止录音')
    await handleStopRecording({ sendMessage: false })
    showNotification('会话切换，录音已停止', 'warning')
    // 等待录音完全停止
    await new Promise(resolve => setTimeout(resolve, 500))
  }
  
  try {
    const data = await api.post(`/sessions/${sessionId}/switch`)
    
    if (data.success) {
      currentSessionId.value = sessionId
      await loadSessionMessages(sessionId)
      showNotification(`已切换到: ${data.session.title}`, 'success')
    }
  } catch (error) {
    console.error('切换会话失败:', error)
    showNotification('切换会话失败', 'error')
  }
}

// 删除会话
async function handleDeleteSession(sessionId) {
  try {
    const data = await api.delete(`/sessions/${sessionId}`)
    
    if (data.success) {
      await loadSessions()
      showNotification('会话已删除', 'success')
    }
  } catch (error) {
    console.error('删除会话失败:', error)
    showNotification(error.response?.data?.detail || '删除会话失败', 'error')
  }
}

// 更新会话标题
async function handleUpdateTitle(sessionId, newTitle) {
  try {
    console.log('更新会话标题:', sessionId, newTitle)
    
    // 使用 query 参数发送
    const response = await api.put(`/sessions/${sessionId}/title?title=${encodeURIComponent(newTitle)}`)
    
    console.log('更新标题响应:', response)
    
    if (response.success) {
      // 更新本地会话列表中的标题
      const session = sessions.value.find(s => s.id === sessionId)
      if (session) {
        session.title = newTitle
      }
      showNotification('标题已更新', 'success')
    }
  } catch (error) {
    console.error('更新标题失败:', error)
    console.error('错误详情:', error.response?.data)
    
    // 如果是 404，可能是会话不存在，刷新会话列表
    if (error.response?.status === 404) {
      showNotification('会话不存在，正在刷新列表', 'error')
      await loadSessions()
    } else {
      showNotification('更新标题失败: ' + (error.response?.data?.detail || error.message), 'error')
    }
  }
}

function getAssistantEntries(message) {
  const parallel = message.parallel_models || message.models
  if (Array.isArray(parallel) && parallel.length > 0) {
    return parallel
      .filter(item => item?.content)
      .map(item => {
        const model = item.model_info?.name || item.model || '模型'
        const source = item.model_info?.provider || item.source_name
        const label = source && source !== 'unknown' ? `${source} · ${model}` : model
        return { label, content: item.content }
      })
  }

  const model = message.model_info?.name
  const source = message.model_info?.provider
  const modelLabel = model && source && source !== 'unknown' ? `${source} · ${model}` : model
  return message.content
    ? [{ label: modelLabel || 'AI', content: message.content }]
    : []
}

function groupSessionMessages(session) {
  const groups = []
  const groupsByUserId = new Map()
  let latestGroup = null
  for (const message of session.messages || []) {
    if (message.role === 'user') {
      latestGroup = { question: message, answers: [] }
      groups.push(latestGroup)
      if (message.id) groupsByUserId.set(message.id, latestGroup)
    } else if (message.role === 'assistant') {
      const group = groupsByUserId.get(message.parent_id) || latestGroup
      if (group) group.answers.push(...getAssistantEntries(message))
    }
  }
  return groups
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}

function clipboardMarkdownHtml(content) {
  const container = document.createElement('div')
  container.innerHTML = renderMarkdown(content || '')
  container.querySelectorAll('.copy-button').forEach(button => button.remove())
  return container.innerHTML
}

function sessionAttachmentUrl(sessionId, attachment) {
  return privateUrl(`/api/attachments/${encodeURIComponent(sessionId)}/${encodeURIComponent(attachment.id)}`)
}

async function buildExportAttachments(sessionId, attachments = []) {
  const result = []
  for (const [index, attachment] of attachments.entries()) {
    const relativeUrl = sessionAttachmentUrl(sessionId, attachment)
    const absoluteUrl = new URL(relativeUrl, window.location.origin).href
    let imageUrl = absoluteUrl
    try {
      const response = await authFetch(relativeUrl)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      imageUrl = await blobToDataUrl(await response.blob())
    } catch (error) {
      console.warn('导出时无法内嵌图片，保留图片链接:', error)
    }
    result.push({ label: `截图 ${index + 1}`, absoluteUrl, imageUrl })
  }
  return result
}

async function buildSessionCopyDocument(session, command) {
  const textSections = []
  const htmlSections = []
  const groups = groupSessionMessages(session)

  for (const [index, group] of groups.entries()) {
    const number = index + 1
    const includeQuestion = command !== 'copy-assistant'
    const includeAnswers = command !== 'copy-user'
    const attachments = includeQuestion
      ? await buildExportAttachments(session.id, group.question.attachments)
      : []

    const textParts = [`# 问题 ${number}`]
    const htmlParts = [`<h1>问题 ${number}</h1>`]

    if (includeQuestion) {
      if (group.question.content) {
        textParts.push(group.question.content)
        htmlParts.push(clipboardMarkdownHtml(group.question.content))
      }
      if (attachments.length > 0) {
        textParts.push(attachments.map(image => (
          `![${image.label}](${image.absoluteUrl})`
        )).join('\n'))
        htmlParts.push(attachments.map(image => (
          `<p><img src="${escapeHtml(image.imageUrl)}" alt="${escapeHtml(image.label)}" style="max-width:100%;height:auto;" /></p>`
        )).join(''))
      }
    }

    if (includeAnswers) {
      for (const answer of group.answers) {
        textParts.push(`## 回答 · ${answer.label}`, answer.content)
        htmlParts.push(
          `<h2>回答 · ${escapeHtml(answer.label)}</h2>`,
          clipboardMarkdownHtml(answer.content)
        )
      }
    }

    if ((includeQuestion && (group.question.content || attachments.length)) || (includeAnswers && group.answers.length)) {
      textSections.push(textParts.join('\n\n'))
      htmlSections.push(`<article>${htmlParts.join('')}</article>`)
    }
  }

  return {
    text: textSections.join('\n\n---\n\n'),
    html: `<div>${htmlSections.join('<hr>')}</div>`
  }
}

async function handleCopySession(sessionId, command) {
  try {
    const session = await api.get(`/sessions/${sessionId}`)
    const document = await buildSessionCopyDocument(session, command)
    if (!document.text) {
      showNotification('该会话没有可复制的对应消息', 'warning')
      return
    }
    await copyRichContent(document.text, document.html)
    const labels = {
      'copy-user': '发送消息',
      'copy-assistant': '返回消息',
      'copy-all': '全部消息'
    }
    showNotification(`已复制该会话的${labels[command] || '消息'}`, 'success')
  } catch (error) {
    console.error('复制会话失败:', error)
    showNotification('复制失败: ' + (error.response?.data?.detail || error.message), 'error')
  }
}

async function handleMergeSessionAudio(sessionId) {
  try {
    const response = await authFetch(`/api/sessions/${sessionId}/audio/merged`)
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || '合并录音失败')
    }

    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `session-${sessionId}-audio.wav`
    document.body.appendChild(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    showNotification('录音已按录制顺序合并并下载', 'success')
  } catch (error) {
    console.error('合并录音失败:', error)
    showNotification(error.message || '合并录音失败', 'error')
  }
}

// 消息更新后重新加载
async function handleMessageUpdated() {
  if (currentSessionId.value) {
    await loadSessionMessages(currentSessionId.value)
    await loadSessions() // 更新会话列表（更新时间等）
    showNotification('消息已更新', 'success')
  }
}

// 重新生成消息（新版本 - 调用新的后端接口）
async function handleRegenerateMessage({ messageId, messageIndex, newContent, attachmentIds, model, reasoningEffort, targeted = false, preserveAnswer = false }) {
  if (stoppingResponses.value) return
  const regenerationSessionId = currentSessionId.value
  const questionReference = editedQuestionReference(messages.value, messageId, messageIndex)
  if (sceneSwitching.value && !preserveAnswer) return showNotification('正在切换场景，请稍候', 'warning')
  // Stop all old streams and let their cleanup finish before inserting a new answer.
  // A later edit supersedes an earlier edit still waiting for cancellation.
  const version = ++restartVersion
  restartingResponse.value = true
  try {
    await interruptAnswerStreams(abortController.value, captureControllers)
    if (version !== restartVersion || currentSessionId.value !== regenerationSessionId) return
    if (sceneSwitching.value && !preserveAnswer) return
    messageId = await resolveEditedQuestionId(questionReference, () => api.get(`/sessions/${regenerationSessionId}`))
  } catch (error) {
    showNotification(error.message || '读取待编辑的问题失败', 'error')
    return
  } finally {
    if (version === restartVersion) restartingResponse.value = false
  }
  if (version !== restartVersion || currentSessionId.value !== regenerationSessionId) return
  if (sceneSwitching.value && !preserveAnswer) return
  const targetIndex = messageId && questionReference
    ? findEditedQuestionIndex(messages.value, questionReference, messageId) : -1
  if (targetIndex === -1) {
    showNotification('问题尚未保存，请重新发送后再编辑', 'error')
    return
  }
  
  // 只删除目标消息的下一条消息（AI 的回答），保留后续对话
  // 1. 记录要插入的位置
  const insertIndex = targetIndex + 1
  
  // 2. 检查下一条消息是否是 assistant 消息，如果是则删除它（这是我们要替换的旧回答）
  if (!targeted && insertIndex < messages.value.length && messages.value[insertIndex].role === 'assistant') {
    messages.value.splice(insertIndex, 1)
    console.log(`📝 临时删除旧回答消息`)
  } else {
    console.log(`📝 没有找到需要删除的回答消息`)
  }
  
  // 3. 立即插入一个空的临时消息，确保后续消息位置正确且不会消失
  const tempMsg = {
    role: 'assistant',
    content: '',
    time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    is_temporary: true,
    is_typing_dots: true // 显示打字机动画
  }
  if (!targeted) messages.value.splice(insertIndex, 0, tempMsg)
  let temporaryMessageIndex = targeted ? -1 : insertIndex
  
  isTyping.value = true
  isSending.value = true
  const regenerateController = streamController()
  abortController.value = regenerateController
  
  // 多模型响应容器
  let modelMessages = []
  let targetedMessage = null
  let refreshPromise = null
  
  console.log('🚀 开始重新生成，等待流式响应...')
  const startTime = Date.now()
  let chunkCount = 0
  
  try {
    const response = await authFetch(`/api/sessions/${currentSessionId.value}/messages/${messageId}/regenerate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ 
        preserve_answer: preserveAnswer,
        message_id: messageId,
        new_content: newContent,
        ...(attachmentIds !== undefined ? { attachment_ids: attachmentIds } : {}),
        ...(model ? { model } : {}),
        ...(reasoningEffort ? { reasoning_effort: reasoningEffort } : {})
      }),
      signal: regenerateController.signal
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    // The backend has accepted the edited question; reflect it while the answer streams.
    if (currentSessionId.value === regenerationSessionId && !preserveAnswer) {
      const question = messages.value.find(message => message.id === messageId && message.role === 'user')
      if (question) question.content = newContent
    }

    
    console.log('✅ 连接成功，开始接收流式数据...')
    
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    
    while (true) {
      const { done, value } = await reader.read()
      
      if (done) {
        if (buffer.trim()) {
          processLine(buffer)
        }
        console.log(`✅ 流式接收完成！总耗时: ${((Date.now() - startTime) / 1000).toFixed(2)}秒`)
        break
      }
      
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      
      for (const line of lines) {
        processLine(line)
      }
    }
    if (refreshPromise) await refreshPromise
    
    function processLine(line) {
      if (regenerateController.signal.aborted) return
      const trimmedLine = line.trim()
      if (!trimmedLine || !trimmedLine.startsWith('data: ')) return
      
      try {
        const jsonStr = trimmedLine.slice(6)
        const data = JSON.parse(jsonStr)
        
        if (data.type === 'provider_request') {
          logProviderRequest(data)
        } else if (data.type === 'targeted_start') {
          targetedMessage = beginTargetedAnswer(messages.value, data)
          if (!targetedMessage) throw new Error('无法定位要重新生成的回答')
        } else if (data.type === 'multi_model_start') {
          console.log('🎯 多模型模式:', data.models)
          
          // 创建一个多模型容器消息
          const multiModelMsg = {
            role: 'assistant',
            is_multi_model: true,
            models: [],
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            is_typing_dots: true // 显示打字机动画
          }
          
          // 为每个模型创建子消息对象
          normalizeStreamTargets(data).forEach((target, index) => {
            const msgObj = {
              content: '',
              model_info: {
                id: target.key,
                name: target.model,
                provider: target.source_name
              },
              model_index: index,
              model: target.model,
              model_key: target.key,
              source_name: target.source_name
            }
            multiModelMsg.models.push(msgObj)
            modelMessages.push(msgObj)
          })
          
          // 替换之前添加的临时消息
          if (temporaryMessageIndex >= 0) {
            messages.value[temporaryMessageIndex] = multiModelMsg
          } else {
            // 兜底：如果没有临时消息索引，则在正确位置插入
            messages.value.splice(insertIndex, 0, multiModelMsg)
            temporaryMessageIndex = insertIndex
          }
          isTyping.value = false
          
          console.log('✅ 多模型容器已替换/创建在位置', temporaryMessageIndex)
          
        } else if (data.type === 'model_start') {
          console.log(`🤖 模型 ${data.model} (索引: ${data.model_index}) 开始响应`)
          
          // 如果是单模型且还没有内容更新，tempMsg 已经在那里了，不需要额外操作
          
        } else if (data.type === 'content' || data.type === 'reasoning') {
          chunkCount++
          
          if (targetedMessage) {
            appendAnswerDelta(targetedMessage, data)
          } else if (data.model_index !== undefined && modelMessages.length > 0) {
            // 多模型模式：更新指定位置的多模型消息
            const multiModelMsg = temporaryMessageIndex >= 0 ? messages.value[temporaryMessageIndex] : null
            
            if (multiModelMsg && multiModelMsg.is_multi_model && multiModelMsg.models[data.model_index]) {
              appendAnswerDelta(multiModelMsg.models[data.model_index], data)
            }
          } else {
            // 单模型模式：更新指定位置的消息（即我们最初创建的 tempMsg）
            if (temporaryMessageIndex >= 0 && messages.value[temporaryMessageIndex]) {
              appendAnswerDelta(messages.value[temporaryMessageIndex], data)
            }
          }
          isTyping.value = false
          
        } else if (data.type === 'model_done') {
          console.log(`✅ 模型 ${data.model} 完成`)
          
        } else if (data.type === 'model_error') {
          console.error('❌ 模型错误:', data.model, data.message)
          const modelLabel = data.source_name ? `${data.source_name} · ${data.model}` : data.model
          showNotification(`模型 ${modelLabel} 错误: ${data.message}`, 'error')
          
        } else if (data.type === 'error') {
          console.error('❌ 收到错误:', data.message)
          showNotification('错误: ' + data.message, 'error')
          
        } else if (data.type === 'done') {
          if (targetedMessage) targetedMessage.is_streaming = false
          isTyping.value = false
          modelMessages = []
          // 重新加载消息以获取完整的、位置正确的数据
          console.log('✅ 重新生成完成，正在刷新消息列表...')
          if (currentSessionId.value) {
            refreshPromise = loadSessionMessages(currentSessionId.value).then(() => {
              console.log('✅ 消息列表已刷新，显示在正确位置')
            }).catch(err => {
              console.error('重新加载消息失败:', err)
            })
          }
        }
      } catch (e) {
        console.error('❌ 解析 SSE 数据失败:', line, e)
      }
    }
    
    // 不显示成功通知，因为消息刷新会有视觉反馈
    
  } catch (error) {
    if (!regenerateController.signal.aborted && error.name !== 'AbortError') {
      console.error('重新生成失败:', error)
      showNotification('重新生成失败: ' + error.message, 'error')
    }
  } finally {
    if (targetedMessage) targetedMessage.is_streaming = false
    try {
      if (refreshPromise) await refreshPromise
      if (currentSessionId.value === regenerationSessionId && !['scene-switch', 'user-stop'].includes(regenerateController.signal.reason)) {
        await loadSessionMessages(regenerationSessionId)
      }
    } finally {
      if (abortController.value === regenerateController) abortController.value = null
      isSending.value = false
      isTyping.value = false
      regenerateController.finish()
      modelMessages = []
      if (!sceneSwitching.value && captureQueue.value.length && !drainingCaptures) queueMicrotask(drainCaptureQueue)
    }
  }
}

// 消息删除后重新加载
async function handleMessageDeleted() {
  if (currentSessionId.value) {
    await loadSessionMessages(currentSessionId.value)
    await loadSessions() // 更新会话列表（更新时间等）
    showNotification('消息已删除', 'success')
  }
}

// 通知
function showNotification(message, type = 'info', duration = 3000) {
  ElMessage({ message, type, duration, showClose: type === 'error', grouping: true })
}

// 解析快捷键配置
function parseHotkey(hotkeyStr) {
  const parts = hotkeyStr.toLowerCase().split('+')
  return {
    ctrl: parts.includes('ctrl'),
    alt: parts.includes('alt'),
    shift: parts.includes('shift'),
    key: parts[parts.length - 1]
  }
}

const escapeGesture = createEscapeGesture({
  single: () => {
    if (!isRecording.value || isProcessingRecording.value || recordingPhase.value !== 'idle') return
    isProcessingRecording.value = true
    handleStopRecording({ sendMessage: false })
      .catch(error => console.error('Esc 停止识别失败:', error))
      .finally(() => { isProcessingRecording.value = false })
  },
  double: clearComposerOnly
})

// 键盘事件处理
function handleKeyDown(event) {
  if (escapeGesture.handle(event)) {
    if (isRecording.value) {
      event.preventDefault()
      event.stopPropagation()
    }
    return
  }

  // 从配置中读取快捷键设置
  const hotkeyConfig = config.value.hotkey?.local_toggle || 'alt+e'
  const hotkey = parseHotkey(hotkeyConfig)
  
  // 检查是否匹配配置的快捷键
  const ctrlMatch = hotkey.ctrl ? event.ctrlKey : !event.ctrlKey
  const altMatch = hotkey.alt ? event.altKey : !event.altKey
  const shiftMatch = hotkey.shift ? event.shiftKey : !event.shiftKey
  const eventKey = (event.key || '').toLowerCase()
  const eventCode = (event.code || '').toLowerCase()
  let expectedCode = ''
  if (/^[a-z]$/.test(hotkey.key)) {
    expectedCode = `key${hotkey.key}`
  } else if (/^[0-9]$/.test(hotkey.key)) {
    expectedCode = `digit${hotkey.key}`
  }
  // macOS 的 Option+E 是重音符死键，event.key 会变成 "Dead"；
  // 同时检查物理键码 KeyE，确保 Alt+E 仍能正常触发。
  const keyMatch = eventKey === hotkey.key || (expectedCode && eventCode === expectedCode)
  
  if (ctrlMatch && altMatch && shiftMatch && keyMatch) {
    event.preventDefault() // 阻止浏览器默认行为（包括刷新）
    event.stopPropagation() // 阻止事件冒泡
    if (event.repeat) return
    handleToggleRecording()
  }
}

// 页面可见性变化处理
function handleVisibilityChange() {
  if (document.hidden && isRecording.value) {
    console.log('⚠️ [页面隐藏] 检测到页面被隐藏，停止录音')
    handleStopRecording({ sendMessage: false })
    showNotification('页面切换，录音已停止', 'warning')
  }
}

// 页面卸载前处理（关闭、刷新、回退等）
function handleBeforeUnload(event) {
  if (isRecording.value) {
    console.log('⚠️ [页面卸载] 检测到页面即将卸载，停止录音')
    // 发送停止请求（使用 sendBeacon 确保在页面卸载时也能发送）
    authFetch('/api/recording/stop', { method: 'POST', keepalive: true }).catch(() => {})
    isRecording.value = false
    // 显示确认对话框（某些浏览器会显示）
    event.preventDefault()
    event.returnValue = '正在录音中，确定要离开吗？'
    return event.returnValue
  }
}

// 监听浏览器历史记录变化（回退/前进）
function handlePopState() {
  if (isRecording.value) {
    console.log('⚠️ [历史记录变化] 检测到浏览器回退/前进，停止录音')
    handleStopRecording({ sendMessage: false })
    showNotification('页面导航，录音已停止', 'warning')
  }
}

// 初始化
onMounted(async () => {
  await loadConfig()
  await loadSessions()  // 加载会话列表
  
  // 首次使用时显示设置
  const hasConfig = userStorage.getItem('hasConfig')
  if (!hasConfig) {
    showSettings.value = true
    userStorage.setItem('hasConfig', 'true')
  }
  
  // 添加键盘事件监听
  window.addEventListener('keydown', handleKeyDown)
  
  // 添加页面可见性监听
  document.addEventListener('visibilitychange', handleVisibilityChange)
  
  // 添加页面卸载监听（关闭、刷新、回退等）
  window.addEventListener('beforeunload', handleBeforeUnload)
  
  // 添加浏览器历史记录变化监听（回退/前进）
  window.addEventListener('popstate', handlePopState)
  
  // 显示快捷键提示（仅首次）
  const hasSeenHotkeyTip = userStorage.getItem('hasSeenHotkeyTip')
  if (!hasSeenHotkeyTip) {
    const hotkeyConfig = config.value.hotkey?.local_toggle || 'alt+e'
    const hotkeyDisplay = hotkeyConfig.split('+').map(k => 
      k.charAt(0).toUpperCase() + k.slice(1)
    ).join('+')
    
    setTimeout(() => {
      showNotification(`💡 提示：按 ${hotkeyDisplay} 可以快速开始/停止录音`, 'info', 5000)
      userStorage.setItem('hasSeenHotkeyTip', 'true')
    }, 2000)
  }
})

// 组件卸载时移除事件监听
onUnmounted(() => {
  escapeGesture.reset()
  window.removeEventListener('keydown', handleKeyDown)
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  window.removeEventListener('beforeunload', handleBeforeUnload)
  window.removeEventListener('popstate', handlePopState)

  displayCapture?.stop()
  displayCapture = null
  
  // 停止状态轮询
  if (recordingStatusInterval) {
    clearInterval(recordingStatusInterval)
    recordingStatusInterval = null
  }
  
  // 如果正在录音，停止录音
  if (isRecording.value) {
    console.log('⚠️ [组件卸载] 组件卸载时正在录音，停止录音')
    handleStopRecording({ sendMessage: false })
  }
})
</script>

<style scoped>
.recording-mode-picker { display: flex; align-items: center; gap: 12px; color: #334155; font-size: 13px; }
.recording-mode-picker select { min-width: 150px; padding: 5px 8px; border: 1px solid #cbd5e1; border-radius: 6px; background: white; color: #334155; }
.recording-mode-summary { display: flex; flex-direction: column; gap: 4px; padding: 10px 12px; background: #eff6ff; color: #1e40af; border-radius: 8px; }
.recording-device-warning { color: #92400e; }
.recording-defaults { align-self: flex-start; color: #4f46e5; font-size: 12px; }
.recording-defaults:disabled { opacity: .5; }
.recording-input-options { display: flex; flex-direction: column; gap: 12px; padding-bottom: 12px; border-bottom: 1px solid #e5e7eb; }
.chat-view-container {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  background: #fafafa;
}

.chat-view {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  background: #fafafa;
}

.scene-row { flex-shrink: 0; padding: 8px 36px; background: var(--paper); }
.composer-overlay { position: absolute; top: 0; left: 0; right: 0; z-index: 35; }
.chat-main {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  width: 100%;
  min-width: 0;
  background: #f7f9fc;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes fadeOut {
  from {
    opacity: 1;
    transform: translateY(0);
  }
  to {
    opacity: 0;
    transform: translateY(-10px);
  }
}
</style>

<style scoped>
.answer-highlight-controls { display: inline-flex; align-items: center; min-width: 116px; }
.answer-toggle { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; font-size: 13px; white-space: nowrap; }
</style>
