<template>
  <div class="chat-view-container">
    <!-- 会话侧边栏 -->
    <SessionSidebar
      :sessions="sessions"
      :current-session-id="currentSessionId"
      @open-settings="showSettings = true"
      @create-session="handleCreateSession"
      @switch-session="handleSwitchSession"
      @delete-session="handleDeleteSession"
      @update-title="handleUpdateTitle"
    />
    
    <!-- 主内容区 -->
    <div class="chat-view">
      <!-- 顶部导航栏 -->
      <NavBar 
        :config="config"
        @open-prompt-lab="$emit('open-prompt-lab')"
        @open-session-settings="showSessionSettings = true" 
        @clear-chat="handleClearChat" 
      />
      
      <!-- 输入区域 -->
      <InputArea
        v-model="inputMessage"
        :is-sending="isSending"
        @send="handleSendMessage"
      />

      <!-- 主聊天区域 -->
      <div class="chat-main">
        <MessageList 
          :messages="messages"
          :is-typing="isTyping"
          :current-session-id="currentSessionId"
          :font-size="messageDisplaySettings.fontSize"
          :line-height="messageDisplaySettings.lineHeight"
          ref="messageListRef"
          @message-updated="handleMessageUpdated"
          @message-deleted="handleMessageDeleted"
          @messages-deleted="handleMessageDeleted"
          @regenerate="handleRegenerateMessage"
        />
      </div>
      
      <!-- 可拖动的语音按钮 -->
      <VoiceButton
        :is-recording="isRecording"
        :audio-stream="audioStream"
        @toggle="handleToggleRecording"
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
      @close="showSessionSettings = false"
      @updated="handleSessionConfigUpdated"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import { ElMessageBox } from 'element-plus'
import NavBar from '../components/NavBar.vue'
import MessageList from '../components/MessageList.vue'
import InputArea from '../components/InputArea.vue'
import VoiceButton from '../components/VoiceButton.vue'
import SettingsModal from '../components/SettingsModal.vue'
import SessionSidebar from '../components/SessionSidebar.vue'
import SessionSettingsSidebar from '../components/SessionSettingsSidebar.vue'
import api from '../utils/api'

defineEmits(['open-prompt-lab'])

// 状态
const messages = ref([])
const inputMessage = ref('')
const isSending = ref(false)
const isRecording = ref(false)
const isTyping = ref(false)
const showSettings = ref(false)
const showSessionSettings = ref(false)
const messageListRef = ref(null)
const audioStream = ref(null)
const abortController = ref(null) // 用于取消请求

// 会话管理状态
const sessions = ref([])
const currentSessionId = ref(null)

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
  if (abortController.value) {
    console.log('🛑 用户主动打断回答')
    abortController.value.abort()
    abortController.value = null
  }
  isSending.value = false
  isTyping.value = false
}

// 发送消息
async function handleSendMessage() {
  // 如果正在发送
  if (isSending.value) {
    // 如果输入框有新内容，先打断再发送新消息
    if (inputMessage.value.trim()) {
      const newMessage = inputMessage.value.trim()
      stopCurrentResponse()
      // 等待状态重置
      await new Promise(resolve => setTimeout(resolve, 100))
      inputMessage.value = newMessage
      // 递归调用发送新消息
      return handleSendMessage()
    } else {
      // 输入框为空，只是打断
      stopCurrentResponse()
      return
    }
  }
  
  if (!inputMessage.value.trim()) return
  
  const message = inputMessage.value.trim()
  inputMessage.value = ''
  
  // 添加用户消息
  messages.value.push({
    role: 'user',
    content: message,
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
  abortController.value = new AbortController()
  
  // 多模型响应容器（后端会告诉我们有多少个模型）
  let modelMessages = []  // 存储多个模型的消息对象
  
  console.log('🚀 开始发送消息，等待流式响应...')
  const startTime = Date.now()
  let chunkCount = 0
  let lastChunkTime = startTime
  
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ message }),
      signal: abortController.value.signal
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
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
    
    function processLine(line) {
      const trimmedLine = line.trim()
      if (!trimmedLine || !trimmedLine.startsWith('data: ')) return
      
      try {
        const jsonStr = trimmedLine.slice(6)
        const data = JSON.parse(jsonStr)
        
        if (data.type === 'multi_model_start') {
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
          data.models.forEach((model, index) => {
            // 从模型名称中提取 provider（如 "google/gemini-2.5-flash" -> "google"）
            let provider = 'unknown'
            if (model.includes('/')) {
              provider = model.split('/')[0]
            }
            
            const msgObj = {
              content: '',
              model_info: {
                name: model,
                provider: provider
              },
              model_index: index,
              model: model  // 添加 model 字段
            }
            multiModelMsg.models.push(msgObj)
            modelMessages.push(msgObj)
          })
          
          messages.value.push(multiModelMsg)
          isTyping.value = false
          
        } else if (data.type === 'model_start') {
          // 某个模型开始响应
          console.log(`🤖 模型 ${data.model} 开始响应`)
          
        } else if (data.type === 'content') {
          chunkCount++
          const now = Date.now()
          lastChunkTime = now
          
          if (data.model_index !== undefined && modelMessages.length > 0) {
            // 多模型模式：更新对应索引的消息
            if (modelMessages[data.model_index]) {
              // 直接更新 messages.value 中的多模型消息，触发 Vue 响应式更新
              const multiModelMsg = messages.value[messages.value.length - 1]
              if (multiModelMsg && multiModelMsg.is_multi_model && multiModelMsg.models[data.model_index]) {
                multiModelMsg.models[data.model_index].content += data.data
              }
            }
          } else {
            // 单模型模式：找到最后一条 assistant 消息
            for (let i = messages.value.length - 1; i >= 0; i--) {
              if (messages.value[i].role === 'assistant') {
                messages.value[i].content += data.data
                break
              }
            }
          }
          isTyping.value = false
          
        } else if (data.type === 'model_done') {
          console.log(`✅ 模型 ${data.model} 完成`)
          
        } else if (data.type === 'model_error') {
          console.error('❌ 模型错误:', data.model, data.message)
          showNotification(`模型 ${data.model} 错误: ${data.message}`, 'error')
          
        } else if (data.type === 'error') {
          console.error('❌ 收到错误:', data.message)
          showNotification('错误: ' + data.message, 'error')
          
        } else if (data.type === 'done') {
          isTyping.value = false
          modelMessages = []  // 清空多模型缓存
          // 重新加载消息以获取完整的带ID的数据
          if (currentSessionId.value) {
            loadSessionMessages(currentSessionId.value).then(() => {
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
    if (error.name === 'AbortError') {
      console.log('✋ 请求已被用户取消')
      showNotification('已停止生成', 'info')
      
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
    abortController.value = null
    modelMessages = []
  }
}

// 语音录音防抖标志
let isProcessingRecording = false
// 记录开始录音时的会话ID，确保停止时发送到正确的会话
let recordingSessionId = null
// 录音状态轮询定时器
let recordingStatusInterval = null

// 检查录音状态（轮询）
async function checkRecordingStatus() {
  try {
    const status = await api.get('/recording/status')

    // Soniox returns interim hypotheses during the stream. Reflect the latest
    // hypothesis in the composer while recording; the stop endpoint still
    // supplies the authoritative final text.
    if (isRecording.value && status.partial_text) {
      inputMessage.value = status.partial_text
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
      await handleStopRecording()
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
    console.error('检查录音状态失败:', error)
  }
}

// 停止录音并获取结果（独立函数，供自动停止和手动停止调用）
async function handleStopRecording({ sendMessage = true } = {}) {
  const stopClickTime = Date.now()
  console.log(`🔴 [停止录音:${new Date(Date.now()).toLocaleTimeString()}.${Date.now() % 1000}] 停止录音: ${new Date(stopClickTime).toLocaleTimeString()}.${stopClickTime % 1000}`)
  
  isRecording.value = false
  showNotification('正在识别...', 'info')
  
  // 停止状态轮询
  if (recordingStatusInterval) {
    clearInterval(recordingStatusInterval)
    recordingStatusInterval = null
  }
  
  // 保存当前录音会话ID（在 finally 之前保存，因为后面是异步操作）
  const targetSessionId = recordingSessionId
  recordingSessionId = null  // 立即清除，允许新的录音
  
  try {
    console.log(`📡 [发送请求:${new Date(Date.now()).toLocaleTimeString()}.${Date.now() % 1000}] 向后端发送 /recording/stop 请求...`)
    const apiStartTime = Date.now()
    
    const data = await api.post('/recording/stop')
    
    const apiEndTime = Date.now()
    const apiDuration = apiEndTime - apiStartTime
    console.log(`✅ [收到响应:${new Date(apiEndTime).toLocaleTimeString()}.${apiEndTime % 1000}] API 请求耗时: ${apiDuration}ms`)
    console.log(`📝 [响应数据:${new Date(Date.now()).toLocaleTimeString()}.${Date.now() % 1000}] success=${data.success}, text="${data.text || ''}"${data.message ? ', message="' + data.message + '"' : ''}`)
    
    if (data.success && data.text) {
      const totalDuration = apiEndTime - stopClickTime
      console.log(`✅ [识别成功:${new Date(Date.now()).toLocaleTimeString()}.${Date.now() % 1000}] 总耗时: ${totalDuration}ms (从点击停止录音 到收到识别的响应结果)`)
      
      inputMessage.value = data.text
      
      // 如果录音时切换了会话，需要切换回原来的会话
      if (targetSessionId && targetSessionId !== currentSessionId.value) {
        console.log(`🔄 [会话切换] 录音期间会话已切换，发送到原始会话: ${targetSessionId}`)
        await handleSwitchSession(targetSessionId)
        // 切换会话会重新加载消息，但不会保留输入框草稿。
        inputMessage.value = data.text
      }

      if (!sendMessage) {
        console.log('📝 [保留草稿] Esc 停止识别，结果保留在输入框且不发送')
        showNotification('识别已停止，文字已保留在输入框，可修改后再发送', 'success', 4000)
        return
      }
      
      console.log(`🚀 [发送消息:${new Date(Date.now()).toLocaleTimeString()}.${Date.now() % 1000}] 准备发送消息给模型...`)
      const sendStartTime = Date.now()
      
      // 不等待 handleSendMessage 完成，让它在后台运行
      // 这样用户可以在 AI 回答期间再次录音
      handleSendMessage().then(() => {
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
  }
}

// 开始录音
async function handleStartRecording() {
  const startClickTime = Date.now()
  console.log(`🟢 [开始录音:${new Date(Date.now()).toLocaleTimeString()}.${Date.now() % 1000}] 点击开始按钮: ${new Date(startClickTime).toLocaleTimeString()}.${startClickTime % 1000}`)
  
  // 如果正在回答，先打断回答
  if (isSending.value) {
    console.log('🛑 [打断回答] 检测到正在回答，先停止当前回答')
    stopCurrentResponse()
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  
  try {
    console.log(`📡 [发送请求:${new Date(Date.now()).toLocaleTimeString()}.${Date.now() % 1000} ] 向后端发送 /recording/start 请求...`)
    const apiStartTime = Date.now()
    
    const response = await api.post('/recording/start')
    
    const apiEndTime = Date.now()
    const apiDuration = apiEndTime - apiStartTime
    console.log(`✅ [录音已启动:${new Date(Date.now()).toLocaleTimeString()}.${Date.now() % 1000}] API 请求耗时: ${apiDuration}ms`)
    
    // ✅ 只有在后端成功启动后才设置前端状态
    if (response.success) {
      isRecording.value = true
      recordingSessionId = currentSessionId.value  // 记录开始录音时的会话ID
      console.log(`📝 [记录会话] 录音开始于会话: ${recordingSessionId}`)
      showNotification('🎤 正在录音：Alt+E 停止并发送，Esc 停止并保留草稿', 'info', 5000)
      
      // 以较短间隔同步 Soniox 的中间 token（停止接口仍返回最终文本）
      recordingStatusInterval = setInterval(checkRecordingStatus, 500)
    } else {
      console.error(`❌ [启动失败] 后端返回失败: ${response.message}`)
      showNotification('启动录音失败: ' + (response.message || '未知错误'), 'error')
    }
  } catch (error) {
    console.error(`❌ [异常:${new Date(Date.now()).toLocaleTimeString()}.${Date.now() % 1000}] 启动录音失败:`, error)
    showNotification('启动录音失败: ' + error.message, 'error')
  }
}

// 语音录音切换（供按钮和快捷键调用）
async function handleToggleRecording() {
  // 防止重复调用
  if (isProcessingRecording) {
    console.warn('⚠️ [防抖] 正在处理录音请求，忽略重复调用')
    return
  }
  
  isProcessingRecording = true
  
  try {
    if (isRecording.value) {
      // 停止录音
      await handleStopRecording({ sendMessage: true })
    } else {
      // 开始录音
      await handleStartRecording()
    }
  } finally {
    isProcessingRecording = false
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
async function loadSessions() {
  try {
    const data = await api.get('/sessions')
    sessions.value = data.sessions || []
    currentSessionId.value = data.current_session_id
    
    // 加载当前会话的消息
    if (currentSessionId.value) {
      await loadSessionMessages(currentSessionId.value)
    }
    
    console.log('会话列表加载成功:', sessions.value.length, '个会话')
  } catch (error) {
    console.error('加载会话列表失败:', error)
    showNotification('加载会话列表失败', 'error')
  }
}

// 加载指定会话的消息
async function loadSessionMessages(sessionId) {
  try {
    const data = await api.get(`/sessions/${sessionId}`)
    messages.value = data.messages || []
    
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
      await loadSessions()
      showNotification('新会话已创建', 'success')
    }
  } catch (error) {
    console.error('创建会话失败:', error)
    showNotification('创建会话失败', 'error')
  }
}

// 切换会话
async function handleSwitchSession(sessionId) {
  if (sessionId === currentSessionId.value) return
  
  // 如果正在录音，先停止录音（除非是录音停止后自动切换回原会话）
  if (isRecording.value) {
    console.log('⚠️ [会话切换] 检测到会话切换，停止录音')
    await handleStopRecording()
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

// 消息更新后重新加载
async function handleMessageUpdated() {
  if (currentSessionId.value) {
    await loadSessionMessages(currentSessionId.value)
    await loadSessions() // 更新会话列表（更新时间等）
    showNotification('消息已更新', 'success')
  }
}

// 重新生成消息（新版本 - 调用新的后端接口）
async function handleRegenerateMessage({ messageId, newContent }) {
  if (isSending.value) {
    showNotification('正在发送中，请稍候', 'warning')
    return
  }
  
  console.log('🔄 开始重新生成:', messageId, newContent)
  
  // 找到要重新生成的消息在列表中的位置
  const targetIndex = messages.value.findIndex(msg => msg.id === messageId)
  if (targetIndex === -1) {
    showNotification('找不到要重新生成的消息', 'error')
    return
  }
  
  // 只删除目标消息的下一条消息（AI 的回答），保留后续对话
  // 1. 记录要插入的位置
  const insertIndex = targetIndex + 1
  
  // 2. 检查下一条消息是否是 assistant 消息，如果是则删除它（这是我们要替换的旧回答）
  if (insertIndex < messages.value.length && messages.value[insertIndex].role === 'assistant') {
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
  messages.value.splice(insertIndex, 0, tempMsg)
  let temporaryMessageIndex = insertIndex
  
  isTyping.value = true
  isSending.value = true
  
  // 多模型响应容器
  let modelMessages = []
  
  console.log('🚀 开始重新生成，等待流式响应...')
  const startTime = Date.now()
  let chunkCount = 0
  
  try {
    const response = await fetch(`/api/sessions/${currentSessionId.value}/messages/${messageId}/regenerate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ 
        message_id: messageId,
        new_content: newContent
      })
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
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
    
    function processLine(line) {
      const trimmedLine = line.trim()
      if (!trimmedLine || !trimmedLine.startsWith('data: ')) return
      
      try {
        const jsonStr = trimmedLine.slice(6)
        const data = JSON.parse(jsonStr)
        
        if (data.type === 'multi_model_start') {
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
          data.models.forEach((model, index) => {
            // 从模型名称中提取 provider（如 "google/gemini-2.5-flash" -> "google"）
            let provider = 'unknown'
            if (model.includes('/')) {
              provider = model.split('/')[0]
            }
            
            const msgObj = {
              content: '',
              model_info: {
                name: model,
                provider: provider
              },
              model_index: index,
              model: model  // 添加 model 字段
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
          
        } else if (data.type === 'content') {
          chunkCount++
          
          if (data.model_index !== undefined && modelMessages.length > 0) {
            // 多模型模式：更新指定位置的多模型消息
            const multiModelMsg = temporaryMessageIndex >= 0 ? messages.value[temporaryMessageIndex] : null
            
            if (multiModelMsg && multiModelMsg.is_multi_model && multiModelMsg.models[data.model_index]) {
              multiModelMsg.models[data.model_index].content += data.data
            }
          } else {
            // 单模型模式：更新指定位置的消息（即我们最初创建的 tempMsg）
            if (temporaryMessageIndex >= 0 && messages.value[temporaryMessageIndex]) {
              messages.value[temporaryMessageIndex].content += data.data
            }
          }
          isTyping.value = false
          
        } else if (data.type === 'model_done') {
          console.log(`✅ 模型 ${data.model} 完成`)
          
        } else if (data.type === 'model_error') {
          console.error('❌ 模型错误:', data.model, data.message)
          showNotification(`模型 ${data.model} 错误: ${data.message}`, 'error')
          
        } else if (data.type === 'error') {
          console.error('❌ 收到错误:', data.message)
          showNotification('错误: ' + data.message, 'error')
          
        } else if (data.type === 'done') {
          isTyping.value = false
          modelMessages = []
          // 重新加载消息以获取完整的、位置正确的数据
          console.log('✅ 重新生成完成，正在刷新消息列表...')
          if (currentSessionId.value) {
            loadSessionMessages(currentSessionId.value).then(() => {
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
    console.error('重新生成失败:', error)
    showNotification('重新生成失败: ' + error.message, 'error')
    // 刷新消息列表以恢复正确状态
    if (currentSessionId.value) {
      loadSessionMessages(currentSessionId.value).catch(err => {
        console.error('恢复消息列表失败:', err)
      })
    }
  } finally {
    isSending.value = false
    isTyping.value = false
    modelMessages = []
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

// 监听会话切换，重新加载消息
watch(currentSessionId, async (newId) => {
  if (newId) {
    await loadSessionMessages(newId)
  }
})

// 通知
function showNotification(message, type = 'info', duration = 3000) {
  const colors = {
    'success': 'bg-green-500',
    'error': 'bg-red-500',
    'info': 'bg-blue-500'
  }
  
  const notification = document.createElement('div')
  notification.className = `fixed top-4 right-4 ${colors[type]} text-white px-6 py-3 rounded-lg shadow-lg z-50 max-w-md`
  notification.style.animation = 'fadeIn 0.3s ease-in'
  notification.style.wordWrap = 'break-word'
  notification.style.whiteSpace = 'pre-wrap'
  
  // 如果是错误类型，添加关闭按钮
  if (type === 'error') {
    notification.innerHTML = `
      <div class="flex items-start gap-3">
        <div class="flex-1">${message}</div>
        <button onclick="this.parentElement.parentElement.remove()" class="text-white hover:text-gray-200 font-bold text-lg leading-none">&times;</button>
      </div>
    `
  } else {
    notification.textContent = message
  }
  
  document.body.appendChild(notification)
  
  setTimeout(() => {
    if (notification.parentElement) {
      notification.style.animation = 'fadeOut 0.3s ease-out'
      setTimeout(() => notification.remove(), 300)
    }
  }, duration)
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

// 键盘事件处理
function handleKeyDown(event) {
  // 录音过程中按 Esc：停止并保留识别文本，但不发送给模型。
  // 非录音状态下不拦截 Esc，保留关闭弹窗等默认交互。
  if (event.key === 'Escape' && isRecording.value) {
    event.preventDefault()
    event.stopPropagation()
    if (event.repeat || isProcessingRecording) return

    isProcessingRecording = true
    handleStopRecording({ sendMessage: false })
      .catch(error => {
        console.error('Esc 停止识别失败:', error)
      })
      .finally(() => {
        isProcessingRecording = false
      })
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
    handleStopRecording()
    showNotification('页面切换，录音已停止', 'warning')
  }
}

// 页面卸载前处理（关闭、刷新、回退等）
function handleBeforeUnload(event) {
  if (isRecording.value) {
    console.log('⚠️ [页面卸载] 检测到页面即将卸载，停止录音')
    // 发送停止请求（使用 sendBeacon 确保在页面卸载时也能发送）
    navigator.sendBeacon('/api/recording/stop')
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
    handleStopRecording()
    showNotification('页面导航，录音已停止', 'warning')
  }
}

// 初始化
onMounted(async () => {
  await loadConfig()
  await loadSessions()  // 加载会话列表
  
  // 首次使用时显示设置
  const hasConfig = localStorage.getItem('hasConfig')
  if (!hasConfig) {
    showSettings.value = true
    localStorage.setItem('hasConfig', 'true')
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
  const hasSeenHotkeyTip = localStorage.getItem('hasSeenHotkeyTip')
  if (!hasSeenHotkeyTip) {
    const hotkeyConfig = config.value.hotkey?.local_toggle || 'alt+e'
    const hotkeyDisplay = hotkeyConfig.split('+').map(k => 
      k.charAt(0).toUpperCase() + k.slice(1)
    ).join('+')
    
    setTimeout(() => {
      showNotification(`💡 提示：按 ${hotkeyDisplay} 可以快速开始/停止录音`, 'info', 5000)
      localStorage.setItem('hasSeenHotkeyTip', 'true')
    }, 2000)
  }
})

// 组件卸载时移除事件监听
onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  window.removeEventListener('beforeunload', handleBeforeUnload)
  window.removeEventListener('popstate', handlePopState)
  
  // 停止状态轮询
  if (recordingStatusInterval) {
    clearInterval(recordingStatusInterval)
    recordingStatusInterval = null
  }
  
  // 如果正在录音，停止录音
  if (isRecording.value) {
    console.log('⚠️ [组件卸载] 组件卸载时正在录音，停止录音')
    handleStopRecording()
  }
})
</script>

<style scoped>
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

.chat-main {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
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
