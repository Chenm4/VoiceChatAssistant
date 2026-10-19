<template>
  <div class="session-settings" :class="{ 'is-resizing': isResizing }" :style="{ width: `${panelWidth}px` }">
    <div class="settings-resize-handle" role="separator" aria-label="调整会话设置宽度" aria-orientation="vertical" tabindex="0"
      :aria-valuemin="minimumWidth" :aria-valuemax="maximumWidth" :aria-valuenow="panelWidth"
      title="拖动调整宽度，双击恢复默认"
      @pointerdown="startResize" @dblclick="resetWidth"
      @keydown.left.prevent="setWidth(panelWidth + 20)" @keydown.right.prevent="setWidth(panelWidth - 20)"
      @keydown.home.prevent="setWidth(minimumWidth)" @keydown.end.prevent="setWidth(maximumWidth)">
      <span></span>
    </div>
    <div class="settings-header">
      <div class="title">
        <el-icon><Setting /></el-icon>
        会话设置
      </div>
      <el-button text @click="$emit('close')" class="btn-close" aria-label="关闭会话设置">
        <el-icon><Close /></el-icon>
      </el-button>
    </div>

    <div v-if="!session" class="settings-empty">
      请选择一个会话
    </div>

    <div v-else class="settings-body">
      <div class="section">
        <label class="label">鼠标右键</label>
        <el-radio-group v-model="rightClickAction" aria-label="鼠标右键操作">
          <el-radio-button value="record">语音识别（默认）</el-radio-button>
          <el-radio-button value="photo">拍照</el-radio-button>
        </el-radio-group>
        <div class="model-order-hint">左键语音识别，右键可选择语音识别或拍照。两路输入设备在标题栏的输入设置中分别选择。</div>
      </div>
      <div class="section">
        <div class="label-with-tag">
          <label class="label">模型选择</label>
          <el-tag size="small" type="info">支持跨配置源并行</el-tag>
        </div>
        <el-select 
          v-model="selectedModels" 
          multiple 
          collapse-tags
          collapse-tags-tooltip
          placeholder="选择一个或多个模型" 
          style="width: 100%"
        >
          <el-option-group
            v-for="source in config.sources"
            :key="source.name"
            :label="source.name"
          >
            <el-option
              v-for="model in source.models"
              :key="modelTargetKey(source.name, model)"
              :label="`${source.name} · ${model}`"
              :value="modelTargetKey(source.name, model)"
            />
          </el-option-group>
        </el-select>
        <div class="model-order-hint">
          <el-icon><InfoFilled /></el-icon>
          可以从不同配置源同时选择模型；每个模型使用所属配置源的 API 地址和密钥。
        </div>
        <div v-if="selectedModels.length > 1" class="model-order-hint">
          <el-icon><InfoFilled /></el-icon>
          拖拽下方标签可调整模型显示顺序
        </div>
      </div>

      <!-- 模型排序区域 -->
      <div v-if="selectedModels.length > 1" class="section">
        <label class="label">模型顺序（从左到右）</label>
        <div class="model-tags-container">
          <draggable 
            v-model="selectedModels" 
            :item-key="item => item"
            class="model-tags-list"
            :animation="200"
          >
            <template #item="{ element, index }">
              <el-tag 
                :key="element"
                closable
                @close="removeModel(index)"
                class="model-tag-draggable"
              >
                <el-icon class="drag-handle"><Rank /></el-icon>
                {{ modelTargetLabel(element) }}
              </el-tag>
            </template>
          </draggable>
        </div>
      </div>

      <div v-if="selectedModels.length" class="section reasoning-section">
        <div class="label-with-tag">
          <label class="label">思维链长度</label>
          <el-tag size="small" type="info">按模型分别设置</el-tag>
        </div>
        <div
          v-for="modelKey in selectedModels"
          :key="modelKey"
          class="reasoning-target"
        >
          <span class="reasoning-model-name">{{ modelTargetLabel(modelKey) }}</span>
          <el-select
            v-model="reasoningEfforts[modelKey]"
            size="small"
            style="width: 145px"
          >
            <el-option
              v-for="option in reasoningOptionsForTarget(modelKey)"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </div>
        <div class="model-order-hint">
          <el-icon><InfoFilled /></el-icon>
          OpenRouter 默认使用 minimal（极低）；其他供应商使用列表首档。
        </div>
      </div>

      <div v-if="selectedModels.length > 1" class="section global-display-section">
        <div class="label-with-tag">
          <label class="label">多模型显示（全局）</label>
          <el-tag size="small" type="success">所有会话生效</el-tag>
        </div>
        <el-radio-group v-model="multiModelDisplayMode" class="display-mode-group">
          <el-radio-button label="parallel">并排显示</el-radio-button>
          <el-radio-button label="focused">单模型切换</el-radio-button>
        </el-radio-group>
        <el-select 
          v-model="defaultDisplayModel" 
          placeholder="选择默认显示模型"
          style="width: 100%"
        >
          <el-option
            v-for="model in selectedModels"
            :key="model"
            :label="modelTargetLabel(model)"
            :value="model"
          />
        </el-select>
        <div class="display-hint">
          <el-icon><InfoFilled /></el-icon>
          并排卡片宽度在回答卡片右边缘拖拽调整，拖完会自动全局保存
        </div>
      </div>

      <div class="section">
        <label class="label">Temperature</label>
        <el-input-number
          v-model="temperature"
          :step="0.1"
          :min="0"
          :max="2"
          :precision="1"
          controls-position="right"
          style="width: 100%"
        />
      </div>

      <div class="section">
        <label class="label">Top P</label>
        <el-input-number
          v-model="topP"
          :step="0.05"
          :min="0"
          :max="1"
          :precision="2"
          controls-position="right"
          style="width: 100%"
        />
      </div>

      <div class="section">
        <label class="label">历史上下文轮数</label>
        <el-input-number
          v-model="contextTurns"
          :min="1"
          :max="100"
          :step="1"
          controls-position="right"
          style="width: 100%"
        />
        <div class="prompt-hint">
          每轮按一条用户问题计算；默认只发送最近 15 轮历史问题。
        </div>
      </div>

      <div class="section">
        <label class="label">历史上下文最大 Token 数</label>
        <el-input-number
          v-model="contextChars"
          :min="1000"
          :max="200000"
          :step="1000"
          controls-position="right"
          style="width: 100%"
        />
        <div class="prompt-hint">
          轮数和 Token 数同时生效，优先去掉更早的历史内容。Token 使用开源分词库计算；非 OpenAI 模型使用通用分词规则。
        </div>
      </div>

      <div class="section context-assistant-option">
        <div class="prompt-hint">历史问题按 user 消息逐条发送，只回答最后一个问题；历史 AI 回答不发送给模型。</div>
      </div>

      <div class="section display-settings-section">
        <div class="label-with-tag">
          <label class="label">消息显示</label>
          <el-tag size="small" type="success">当前会话</el-tag>
        </div>

        <div class="display-control">
          <div class="display-control-header">
            <span>正文字号</span>
            <strong>{{ displayFontSize }} px</strong>
          </div>
          <el-slider
            v-model="displayFontSize"
            :min="12"
            :max="72"
            :step="1"
            :show-tooltip="true"
          />
        </div>

        <div class="display-control">
          <div class="display-control-header">
            <span>行间距</span>
            <strong>{{ Number(displayLineHeight).toFixed(1) }}</strong>
          </div>
          <el-slider
            v-model="displayLineHeight"
            :min="1"
            :max="3"
            :step="0.1"
            :show-tooltip="true"
          />
        </div>

        <div
          class="display-preview"
          :style="{
            fontSize: `${displayFontSize}px`,
            lineHeight: displayLineHeight
          }"
        >
          字体与行间距预览：MySQL、Redis、RabbitMQ、JVM
        </div>
        <div class="prompt-hint">
          保存后立即应用到当前会话的用户消息、AI 回答、标题和代码。
        </div>
      </div>

      <div class="section screenshot-prompt-section">
        <div class="label-with-tag">
          <label class="label">截图答题提示词</label>
          <el-tag size="small" type="success">当前会话</el-tag>
        </div>
        <el-input
          v-model="screenshotPrompt"
          type="textarea"
          :rows="5"
          resize="vertical"
          maxlength="4000"
          show-word-limit
          placeholder="设置点击截图按钮时发送给 AI 的基础指令"
        />
        <div class="prompt-hint neutral-hint">
          <el-icon><InfoFilled /></el-icon>
          点击截图按钮后会直接发送此提示词；输入框中的文字会作为补充要求追加。
        </div>
      </div>

      <div class="section">
        <div class="label-with-tag">
          <label class="label">系统提示词（所有场景共用）</label>
          <el-tag size="small" type="warning">影响AI行为</el-tag>
        </div>
        <el-select 
          v-model="selectedPromptTemplate" 
          @change="handlePromptTemplateChange"
          placeholder="选择预设模板" 
          style="width: 100%; margin-bottom: 8px"
        >
          <el-option label="无（使用默认）" value="" />
          <el-option
            v-if="promptTemplateId"
            :label="`${selectedTemplateName} · v${promptTemplateVersion || 1}（会话快照）`"
            :value="`snapshot:${promptTemplateId}`"
          />
          <el-option 
            v-for="template in promptTemplates" 
            :key="template.id || template.name"
            :label="template.name" 
            :value="template.id || template.name"
          />
          <el-option label="自定义..." value="custom" />
        </el-select>
        <el-input
          v-model="systemPrompt"
          type="textarea"
          :rows="4"
          placeholder="输入自定义系统提示词（可选）&#10;&#10;例如：你是一个专业的编程助手，擅长解答技术问题..."
          style="width: 100%"
          @input="handleSystemPromptInput"
        />
        <div class="prompt-hint">
          <el-icon><InfoFilled /></el-icon>
          实验室更新不会自动覆盖会话快照。选择新版或点击「应用最新版」后，保存即可生效；直接编辑会转为自定义。
        </div>
        <div v-if="promptTemplateId" class="template-snapshot">
          <div>
            <el-tag size="small" type="primary">模板快照</el-tag>
            <span>{{ selectedTemplateName }} · v{{ promptTemplateVersion || 1 }}</span>
            <el-button v-if="hasNewerPromptTemplate" size="small" @click="applyLatestPromptTemplate">
              应用最新版 v{{ latestPromptTemplate.version }}
            </el-button>
          </div>
          <div class="user-prompt-preview">
            User Prompt：{{ displayUserPromptTemplate }}
          </div>
        </div>
      </div>

      <div v-if="session?.session_config?.active_scene" class="section">
        <label class="label">当前场景：{{ session.session_config.active_scene.name }}</label>
        <p class="prompt-hint">以下内容与「管理场景」同步，追加到系统提示词末尾，不放入用户问题、不随历史轮数叠加。默认背景资料在恢复默认后使用。</p>
        <label class="label">场景提示词</label>
        <el-input v-model="sceneRules" type="textarea" :rows="4" resize="vertical" />
        <label class="label" style="margin-top:12px">项目资料</label>
        <el-input v-model="sceneBackground" type="textarea" :rows="6" resize="vertical" />
        <details style="margin-top:12px"><summary>查看系统提示词与场景拼接预览</summary><pre style="white-space:pre-wrap">{{ effectiveScenePrompt }}</pre></details>
      </div>
      <div v-else class="section">
        <div class="label-with-tag">
          <label class="label">个人与项目背景资料</label>
          <el-tag size="small" :type="backgroundMode === 'shared' ? 'success' : 'info'">
            {{ backgroundMode === 'shared' ? '全局共享' : '当前会话' }}
          </el-tag>
        </div>
        <el-radio-group v-model="backgroundMode" class="background-mode-group">
          <el-radio-button label="shared">共享背景</el-radio-button>
          <el-radio-button label="custom">会话专用</el-radio-button>
          <el-radio-button label="none">不发送</el-radio-button>
        </el-radio-group>

        <template v-if="backgroundMode === 'shared'">
          <el-input
            v-model="sharedBackground"
            type="textarea"
            :rows="9"
            resize="vertical"
            :disabled="sharedBackgroundLoading"
            placeholder="填写所有会话和八股实验室共用的个人、实习与项目资料。"
            @input="sharedBackgroundTouched = true"
          />
          <div class="shared-background-warning">
            <el-icon><InfoFilled /></el-icon>
            这里是真正的全局共享资料。修改并保存后，会同步影响八股实验室以及所有使用“共享背景”的会话。
          </div>
        </template>

        <template v-else-if="backgroundMode === 'custom'">
          <el-input
            v-model="backgroundContext"
            type="textarea"
            :rows="9"
            resize="vertical"
            placeholder="仅为当前会话填写实习、项目、职责和技术难点。"
          />
          <div class="prompt-hint neutral-hint">
            <el-icon><InfoFilled /></el-icon>
            此内容只保存在当前会话，不会改动八股实验室的共享背景。
          </div>
        </template>

        <div v-else class="background-disabled-hint">
          当前会话不会向模型发送个人、实习或项目背景，适合纯技术八股问题。
        </div>
      </div>

      <div class="save-status" :class="{ dirty: isDirty }">
        <el-icon><InfoFilled /></el-icon>
        <div>
          <strong>{{ isDirty ? '存在未保存修改' : '当前配置已生效' }}</strong>
          <span v-if="isDirty">当前请求仍使用上次保存的配置。</span>
          <span v-else>{{ effectiveConfigSummary }}</span>
        </div>
      </div>

      <div class="actions">
        <el-button type="primary" @click="handleSave" :loading="saving" style="width: 100%" class="action-button">
          <span class="button-content">
            <el-icon><Select /></el-icon>
            <span>保存会话配置</span>
          </span>
        </el-button>
        <el-button @click="handleReset" :disabled="saving" style="width: 100%" class="action-button">
          使用全局配置
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { userStorage } from '../utils/auth'

import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { Setting, Close, InfoFilled, Select, Rank } from '@element-plus/icons-vue'
import draggable from 'vuedraggable'
import api from '../utils/api'
import { ElMessage } from 'element-plus'

const props = defineProps({
  config: {
    type: Object,
    required: true
  },
  session: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['close', 'updated', 'resize'])

const WIDTH_KEY = 'sessionSettingsWidth'
const viewportWidth = ref(window.innerWidth)
const maximumWidth = computed(() => Math.min(720, Math.max(0, viewportWidth.value - (viewportWidth.value > 1100 ? 600 : 30))))
const minimumWidth = computed(() => Math.min(320, maximumWidth.value))
const panelWidth = ref(370)
const isResizing = ref(false)
let activePointer = null
let resizeTarget = null
let startX = 0
let startWidth = 370
function setWidth(width, persist = true) {
  panelWidth.value = Math.round(Math.max(minimumWidth.value, Math.min(maximumWidth.value, width)))
  emit('resize', panelWidth.value)
  if (persist) {
    try { userStorage.setItem(WIDTH_KEY, String(panelWidth.value)) } catch { /* Resizing still works without storage. */ }
  }
}
function resetWidth() { setWidth(370) }
function startResize(event) {
  if (event.button !== 0) return
  event.preventDefault()
  activePointer = event.pointerId
  resizeTarget = event.currentTarget
  resizeTarget.setPointerCapture(activePointer)
  startX = event.clientX
  startWidth = panelWidth.value
  isResizing.value = true
  window.addEventListener('pointermove', moveResize)
  window.addEventListener('pointerup', finishResize)
  window.addEventListener('pointercancel', finishResize)
}
function moveResize(event) {
  if (event.pointerId === activePointer) setWidth(startWidth + startX - event.clientX, false)
}
function finishResize(event) {
  if (event && event.pointerId !== activePointer) return
  if (resizeTarget?.hasPointerCapture(activePointer)) resizeTarget.releasePointerCapture(activePointer)
  isResizing.value = false
  activePointer = null
  resizeTarget = null
  window.removeEventListener('pointermove', moveResize)
  window.removeEventListener('pointerup', finishResize)
  window.removeEventListener('pointercancel', finishResize)
  if (event) setWidth(panelWidth.value)
}
function fitViewport() { viewportWidth.value = window.innerWidth; setWidth(panelWidth.value, false) }
onMounted(() => {
  let storedWidth = 370
  try { storedWidth = Number(userStorage.getItem(WIDTH_KEY)) || 370 } catch { /* Use the default. */ }
  setWidth(Number.isFinite(storedWidth) ? storedWidth : 370, false)
  window.addEventListener('resize', fitViewport)
})
onUnmounted(() => { finishResize(); window.removeEventListener('resize', fitViewport) })


const DEFAULT_SCREENSHOT_PROMPT = '请识别截图中的笔试题。回答时请在开头先简要、直接地给出最终答案，然后再逐题说明简要思路；代码题请给出可运行代码并分析时间复杂度和空间复杂度。'

const selectedSource = ref('')
const selectedModels = ref([])  // 改为数组支持多选
const reasoningEfforts = ref({})
const temperature = ref(0.7)
const topP = ref(1)
const contextTurns = ref(15)
const contextChars = ref(12000)
const includeAssistantHistory = ref(false)
const screenshotPrompt = ref(DEFAULT_SCREENSHOT_PROMPT)
const rightClickAction = ref('record')
const displayFontSize = ref(16)
const displayLineHeight = ref(1.7)
const saving = ref(false)
const systemPrompt = ref('')
const sceneRules = ref('')
const sceneBackground = ref('')
const effectiveScenePrompt = computed(() => [
  props.session?.session_config?.active_scene?.use_scene_rules_as_system ? '' : systemPrompt.value.trim(),
  '【当前场景】\n' + (props.session?.session_config?.active_scene?.name || ''),
  sceneRules.value.trim() ? '【场景要求】\n' + sceneRules.value.trim() : '',
  sceneBackground.value.trim() ? '【当前项目资料】\n' + sceneBackground.value.trim() : '',
  '当前场景资料以此处为准，历史项目资料仅供参考，不可混用。'
].filter(Boolean).join('\n\n'))
const backgroundContext = ref('')
const backgroundMode = ref('shared')
const sharedBackground = ref('')
const loadedSharedBackground = ref(null)
const sharedBackgroundLoading = ref(false)
const sharedBackgroundTouched = ref(false)
const selectedPromptTemplate = ref('')
const promptTemplateId = ref('')
const promptTemplateVersion = ref(null)
const userPromptTemplate = ref('')
const baselineState = ref(null)
const initializedSessionId = ref(null)
const MULTI_MODEL_PREFERENCES_KEY = 'multiModelDisplayPreferences'
const DEFAULT_MULTI_MODEL_PREFERENCES = {
  displayMode: 'parallel',
  defaultModel: '',
  cardWidth: 0
}
const multiModelDisplayMode = ref('parallel')
const defaultDisplayModel = ref('')

async function loadSharedPromptTemplates() {
  sharedBackgroundLoading.value = true
  try {
    const catalog = await api.get('/prompt-lab/catalog')
    const sharedTemplates = (catalog.prompts || []).map(prompt => ({
      id: `lab:${prompt.id}`,
      promptId: prompt.id,
      name: `八股 · ${prompt.name} v${prompt.version || 1}`,
      content: prompt.system_prompt,
      version: prompt.version || 1,
      userPromptTemplate: prompt.user_prompt_template || '面试题：{{question}}',
      source: 'lab'
    }))
    promptTemplates.value = [
      ...promptTemplates.value.filter(template => template.source !== 'lab'),
      ...sharedTemplates
    ]

    const catalogBackground = catalog.background?.content || ''
    loadedSharedBackground.value = catalogBackground
    if (!sharedBackgroundTouched.value) {
      sharedBackground.value = catalogBackground
      if (baselineState.value) {
        baselineState.value = {
          ...baselineState.value,
          shared_background: backgroundMode.value === 'shared' ? catalogBackground : null
        }
      }
    }
  } catch (error) {
    console.warn('加载八股实验室提示词失败:', error)
    ElMessage.warning('共享提示词和背景加载失败，当前会话配置仍可编辑')
  } finally {
    sharedBackgroundLoading.value = false
  }
}

// 预设系统提示词模板
const promptTemplates = ref([
  {
    name: '默认助手',
    content: '你是一个友好、专业的AI助手，能够回答各种问题并提供帮助。'
  },
  {
    name: '编程专家',
    content: '你是一个资深的软件工程师，擅长多种编程语言和框架。请用简洁、专业的方式回答技术问题，并在必要时提供代码示例。'
  },
  {
    name: '写作助手',
    content: '你是一个专业的写作助手，擅长文案创作、文章润色和内容优化。请帮助用户改进文字表达，使其更加流畅、生动和有说服力。'
  },
  {
    name: '英语老师',
    content: '你是一位经验丰富的英语教师，擅长英语教学和语言纠错。请用中文解释英语知识点，在回答中适当使用英语例句，并指出用户的语法错误。'
  },
  {
    name: '数学导师',
    content: '你是一位耐心的数学导师，擅长用通俗易懂的方式解释数学概念。请一步步引导用户理解问题，并提供详细的解题过程。'
  },
  {
    name: '创意顾问',
    content: '你是一个富有创意的顾问，善于头脑风暴和创新思维。请提供新颖、有趣的想法和解决方案，帮助用户拓展思路。'
  },
  {
    name: '产品经理',
    content: '你是一个经验丰富的产品经理，擅长需求分析、产品设计和用户体验优化。请从产品和用户的角度提供专业建议。'
  },
  {
    name: '简洁模式',
    content: '请用最简洁的方式回答问题，避免冗长的解释。直接给出关键信息和答案。'
  },
  {
    name: '详细模式',
    content: '请提供详细、全面的回答，包含背景知识、多个角度的分析、具体例子和延伸思考。'
  },
  {
    name: '苏格拉底式教学',
    content: '你是一位采用苏格拉底式教学法的导师。不要直接给出答案，而是通过提问引导用户自己思考和发现答案。'
  }
])

function modelTargetKey(sourceName, model) {
  return `${sourceName}::${model}`
}

function parseModelTargetKey(key) {
  const separatorIndex = String(key).indexOf('::')
  if (separatorIndex < 0) {
    return { source_name: selectedSource.value || props.config.current_source, model: key }
  }
  return {
    source_name: key.slice(0, separatorIndex),
    model: key.slice(separatorIndex + 2)
  }
}

function modelTargetLabel(key) {
  const target = parseModelTargetKey(key)
  return `${target.source_name} · ${target.model}`
}

const OPENAI_REASONING_OPTIONS = [
  { value: 'none', label: '无（最低）' },
  { value: 'minimal', label: '极低' },
  { value: 'low', label: '低' },
  { value: 'medium', label: '中' },
  { value: 'high', label: '高' },
  { value: 'xhigh', label: '极高' }
]

const QWEN_REASONING_OPTIONS = [
  { value: 'none', label: '关闭（最低）' },
  { value: 'low', label: '低' },
  { value: 'medium', label: '中' },
  { value: 'xhigh', label: '极高' }
]

const DEFAULT_REASONING_OPTIONS = [
  { value: 'none', label: '供应商默认（最低）' }
]

function reasoningOptionsForTarget(key) {
  const target = parseModelTargetKey(key)
  const source = props.config.sources.find(item => item.name === target.source_name)
  const identity = `${source?.name || ''} ${source?.base_url || ''} ${target.model}`.toLowerCase()
  if (identity.includes('api.xiaomimimo.com')) {
    return [{ value: 'none', label: '关闭思考' }, { value: 'high', label: '开启思考' }]
  }
  if (identity.includes('openrouter')) {
    return OPENAI_REASONING_OPTIONS.filter(option => option.value !== 'none')
  }
  if (identity.includes('qwen') || identity.includes('dashscope.aliyuncs.com')) {
    return QWEN_REASONING_OPTIONS
  }
  const isOpenAIReasoningModel = /^(gpt-[56]|o[134](?:-|$))/i.test(target.model)
  if (identity.includes('api.openai.com') && isOpenAIReasoningModel) {
    return OPENAI_REASONING_OPTIONS
  }
  return DEFAULT_REASONING_OPTIONS
}

function defaultReasoningEffort(key) {
  return reasoningOptionsForTarget(key)[0].value
}

const selectedModelTargets = computed(() => selectedModels.value.map(key => ({
  ...parseModelTargetKey(key),
  reasoning_effort: reasoningEfforts.value[key] || defaultReasoningEffort(key)
})))

function getFormState() {
  const targets = selectedModelTargets.value
  const firstTarget = targets[0]
  const legacyModels = firstTarget
    ? targets.filter(target => target.source_name === firstTarget.source_name).map(target => target.model)
    : []
  return {
    source_name: firstTarget?.source_name || selectedSource.value,
    models: legacyModels,
    model_targets: targets,
    temperature: Number(temperature.value),
    top_p: Number(topP.value),
    max_history_turns: Number(contextTurns.value),
    max_history_chars: Number(contextChars.value),
    include_assistant_history: false,
    screenshot_prompt: screenshotPrompt.value,
    right_click_action: rightClickAction.value,
    display_font_size: Number(displayFontSize.value),
    display_line_height: Number(displayLineHeight.value),
    system_prompt: systemPrompt.value,
    scene_rules: sceneRules.value,
    scene_background: sceneBackground.value,
    prompt_template_id: promptTemplateId.value,
    prompt_template_version: promptTemplateVersion.value,
    user_prompt_template: userPromptTemplate.value,
    background_mode: backgroundMode.value,
    background_context: backgroundMode.value === 'custom' ? backgroundContext.value : null,
    shared_background: backgroundMode.value === 'shared' ? sharedBackground.value : null,
    multi_model_display_mode: multiModelDisplayMode.value,
    default_display_model: defaultDisplayModel.value
  }
}

function setFormBaseline() {
  baselineState.value = JSON.parse(JSON.stringify(getFormState()))
}

const isDirty = computed(() => {
  if (!baselineState.value) return false
  return JSON.stringify(getFormState()) !== JSON.stringify(baselineState.value)
})

const selectedTemplateName = computed(() => {
  const template = promptTemplates.value.find(item => item.promptId === promptTemplateId.value)
  return template?.name?.replace(/^八股 · /, '').replace(/ v\d+$/, '') || promptTemplateId.value
})

const displayUserPromptTemplate = computed(
  () => userPromptTemplate.value || '面试题：{{question}}'
)

const effectiveConfigSummary = computed(() => {
  let promptSummary = '默认系统提示词'
  if (promptTemplateId.value) {
    promptSummary = `${selectedTemplateName.value} v${promptTemplateVersion.value || 1} 快照`
  } else if (systemPrompt.value) {
    promptSummary = '自定义系统提示词'
  }

  const backgroundSummary = {
    shared: '使用实验室共享背景',
    custom: '使用当前会话专用背景',
    none: '不发送背景资料'
  }[backgroundMode.value]

  return `${promptSummary}；${backgroundSummary}`
})

function loadMultiModelPreferences() {
  try {
    const raw = userStorage.getItem(MULTI_MODEL_PREFERENCES_KEY)
    const preferences = raw ? JSON.parse(raw) : DEFAULT_MULTI_MODEL_PREFERENCES
    multiModelDisplayMode.value = preferences.displayMode || DEFAULT_MULTI_MODEL_PREFERENCES.displayMode
    defaultDisplayModel.value = preferences.defaultModel || ''
  } catch (error) {
    console.warn('加载多模型显示偏好失败:', error)
    multiModelDisplayMode.value = DEFAULT_MULTI_MODEL_PREFERENCES.displayMode
    defaultDisplayModel.value = ''
  }
}

function saveMultiModelPreferences() {
  let current = { ...DEFAULT_MULTI_MODEL_PREFERENCES }
  try {
    const raw = userStorage.getItem(MULTI_MODEL_PREFERENCES_KEY)
    if (raw) {
      current = { ...current, ...JSON.parse(raw) }
    }
  } catch (error) {
    console.warn('读取多模型显示偏好失败，将使用默认值:', error)
  }
  
  const next = {
    ...current,
    displayMode: multiModelDisplayMode.value,
    defaultModel: defaultDisplayModel.value || selectedModels.value[0] || ''
  }
  
  userStorage.setItem(MULTI_MODEL_PREFERENCES_KEY, JSON.stringify(next))
  window.dispatchEvent(new CustomEvent('multi-model-preferences-updated', {
    detail: next
  }))
}

function initFromSession() {
  if (!props.session || !props.config) return
  initializedSessionId.value = props.session.id
  loadMultiModelPreferences()
  const sessionConfig = props.session.session_config
  if (sessionConfig) {
    selectedSource.value = sessionConfig.source_name || props.config.current_source
    // 新格式记录每个模型所属源；旧格式仍按会话的单一 source_name 迁移。
    if (sessionConfig.model_targets?.length > 0) {
      selectedModels.value = sessionConfig.model_targets.map(target => (
        modelTargetKey(target.source_name, target.model)
      ))
    } else if (sessionConfig.models && sessionConfig.models.length > 0) {
      selectedModels.value = sessionConfig.models.map(model => (
        modelTargetKey(selectedSource.value, model)
      ))
    } else if (sessionConfig.model) {
      selectedModels.value = [modelTargetKey(selectedSource.value, sessionConfig.model)]
    } else {
      selectedModels.value = [modelTargetKey(props.config.current_source, props.config.current_model)]
    }
    temperature.value = sessionConfig.temperature ?? 0.7
    topP.value = sessionConfig.top_p ?? 1
    contextTurns.value = sessionConfig.max_history_turns ?? 15
    contextChars.value = sessionConfig.max_history_chars ?? 12000
    includeAssistantHistory.value = false
    rightClickAction.value = sessionConfig.right_click_action || 'record'
    screenshotPrompt.value = sessionConfig.screenshot_prompt || DEFAULT_SCREENSHOT_PROMPT
    displayFontSize.value = sessionConfig.display_font_size ?? 16
    displayLineHeight.value = sessionConfig.display_line_height ?? 1.7
    systemPrompt.value = sessionConfig.system_prompt ?? props.session.system_prompt ?? ''
    sceneRules.value = sessionConfig.active_scene?.rules || ''
    sceneBackground.value = sessionConfig.active_scene?.background || ''
    backgroundContext.value = sessionConfig.background_context || ''
    // 旧会话的 system prompt 往往已经包含背景资料。缺少模式字段时
    // 保持后端的 legacy 语义，不自动再叠加共享背景；新会话由后端明确写入 shared。
    backgroundMode.value = sessionConfig.background_mode || 'none'
    promptTemplateId.value = sessionConfig.prompt_template_id || ''
    promptTemplateVersion.value = sessionConfig.prompt_template_version || null
    userPromptTemplate.value = sessionConfig.user_prompt_template || ''

    if (promptTemplateId.value) {
      selectedPromptTemplate.value = `snapshot:${promptTemplateId.value}`
    } else if (systemPrompt.value) {
      const matchedTemplate = promptTemplates.value.find(
        template => template.source !== 'lab' && template.content === systemPrompt.value
      )
      selectedPromptTemplate.value = matchedTemplate?.name || 'custom'
    } else {
      selectedPromptTemplate.value = ''
    }
  } else {
    selectedSource.value = props.config.current_source
    selectedModels.value = [modelTargetKey(props.config.current_source, props.config.current_model)]
    temperature.value = 0.7
    topP.value = 1
    contextTurns.value = 15
    contextChars.value = 12000
    includeAssistantHistory.value = false
    rightClickAction.value = 'record'
    screenshotPrompt.value = DEFAULT_SCREENSHOT_PROMPT
    displayFontSize.value = 16
    displayLineHeight.value = 1.7
    systemPrompt.value = ''
    backgroundContext.value = ''
    backgroundMode.value = 'shared'
    selectedPromptTemplate.value = ''
    promptTemplateId.value = ''
    promptTemplateVersion.value = null
    userPromptTemplate.value = ''
  }

  sharedBackground.value = loadedSharedBackground.value ?? ''
  sharedBackgroundTouched.value = false
  const savedReasoning = new Map(
    (sessionConfig?.model_targets || []).map(target => [
      modelTargetKey(target.source_name, target.model),
      target.reasoning_effort
    ])
  )
  reasoningEfforts.value = Object.fromEntries(
    selectedModels.value.map(key => [
      key,
      reasoningOptionsForTarget(key).some(option => option.value === savedReasoning.get(key))
        ? savedReasoning.get(key) : defaultReasoningEffort(key)
    ])
  )
  if (selectedModels.value.length > 0 && !selectedModels.value.includes(defaultDisplayModel.value)) {
    defaultDisplayModel.value = selectedModels.value[0]
  }
  setFormBaseline()
}

watch([() => props.session?.id, () => props.session?.session_config], ([sessionId]) => {
  if (!sessionId) return
  initFromSession()
}, { immediate: true })
onMounted(loadSharedPromptTemplates)

watch(selectedModels, (models) => {
  const nextEfforts = { ...reasoningEfforts.value }
  for (const key of models) {
    if (!nextEfforts[key]) nextEfforts[key] = defaultReasoningEffort(key)
  }
  reasoningEfforts.value = nextEfforts
  if (models.length > 0 && !models.includes(defaultDisplayModel.value)) {
    defaultDisplayModel.value = models[0]
  }
}, { deep: true })

function removeModel(index) {
  if (selectedModels.value.length > 1) {
    selectedModels.value.splice(index, 1)
  } else {
    ElMessage.warning('至少需要选择一个模型')
  }
}

function clearPromptTemplateAssociation() {
  promptTemplateId.value = ''
  promptTemplateVersion.value = null
  userPromptTemplate.value = ''
}

const latestPromptTemplate = computed(() => promptTemplates.value.find(
  item => item.source === 'lab' && item.promptId === promptTemplateId.value
))
const hasNewerPromptTemplate = computed(() => latestPromptTemplate.value &&
  latestPromptTemplate.value.version > (promptTemplateVersion.value || 1))

function applyLatestPromptTemplate() {
  if (!latestPromptTemplate.value) return
  selectedPromptTemplate.value = latestPromptTemplate.value.id
  handlePromptTemplateChange()
}

function handlePromptTemplateChange() {
  if (selectedPromptTemplate.value.startsWith('snapshot:')) return
  if (selectedPromptTemplate.value === 'custom') {
    clearPromptTemplateAssociation()
    return
  } else if (selectedPromptTemplate.value === '') {
    systemPrompt.value = ''
    clearPromptTemplateAssociation()
  } else {
    const template = promptTemplates.value.find(t => (t.id || t.name) === selectedPromptTemplate.value)
    if (template) {
      systemPrompt.value = template.content
      if (template.source === 'lab') {
        promptTemplateId.value = template.promptId
        promptTemplateVersion.value = template.version
        userPromptTemplate.value = template.userPromptTemplate
      } else {
        clearPromptTemplateAssociation()
      }
    }
  }
}

function handleSystemPromptInput() {
  selectedPromptTemplate.value = 'custom'
  clearPromptTemplateAssociation()
}

async function handleSave() {
  if (!props.session) return
  if (selectedModels.value.length === 0) {
    ElMessage.warning('请至少选择一个模型')
    return
  }
  if (!screenshotPrompt.value.trim()) {
    ElMessage.warning('截图答题提示词不能为空')
    return
  }
  
  saving.value = true
  try {
    if (
      !props.session.session_config?.active_scene
      && backgroundMode.value === 'shared'
      && sharedBackgroundTouched.value
      && sharedBackground.value !== loadedSharedBackground.value
    ) {
      const savedBackground = await api.patch('/prompt-lab/background', {
        content: sharedBackground.value
      })
      sharedBackground.value = savedBackground.content || ''
      loadedSharedBackground.value = sharedBackground.value
      sharedBackgroundTouched.value = false
    }

    const targets = selectedModelTargets.value
    const firstTarget = targets[0]
    const legacyModels = targets
      .filter(target => target.source_name === firstTarget.source_name)
      .map(target => target.model)
    const payload = {
      active_scene: props.session.session_config?.active_scene ? { ...props.session.session_config.active_scene, rules: sceneRules.value, background: sceneBackground.value } : null,
      scene_common_rules: systemPrompt.value,
      source_name: firstTarget.source_name,
      models: legacyModels,
      model_targets: targets,
      temperature: Number(temperature.value),
      top_p: Number(topP.value),
      max_history_turns: Number(contextTurns.value),
      max_history_chars: Number(contextChars.value),
      include_assistant_history: false,
      screenshot_prompt: screenshotPrompt.value.trim(),
      right_click_action: rightClickAction.value,
      display_font_size: Number(displayFontSize.value),
      display_line_height: Number(displayLineHeight.value),
      answer_highlight_enabled: props.session.session_config?.answer_highlight_enabled ?? false,
      system_prompt: systemPrompt.value || null,
      prompt_template_id: promptTemplateId.value || null,
      prompt_template_version: promptTemplateId.value ? promptTemplateVersion.value : null,
      user_prompt_template: promptTemplateId.value ? (userPromptTemplate.value || null) : null,
      background_mode: backgroundMode.value,
      background_context: backgroundMode.value === 'custom'
        ? (backgroundContext.value || null)
        : null
    }
    const response = await api.put(`/sessions/${props.session.id}/config`, payload)
    if (!response.success || response.config?.right_click_action !== payload.right_click_action) {
      throw new Error('后端未保存右键操作，请重启后端服务后重试')
    }
    if (response.success) {
      saveMultiModelPreferences()
      setFormBaseline()
      ElMessage.success('会话配置已保存')
      emit('updated')
    }
  } catch (error) {
    ElMessage.error('保存会话配置失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    saving.value = false
  }
}

function handleReset() {
  selectedSource.value = props.config.current_source
  selectedModels.value = [modelTargetKey(props.config.current_source, props.config.current_model)]
  reasoningEfforts.value = {
    [selectedModels.value[0]]: defaultReasoningEffort(selectedModels.value[0])
  }
  temperature.value = 0.7
  topP.value = 1
  contextTurns.value = 15
  contextChars.value = 12000
  includeAssistantHistory.value = false
  screenshotPrompt.value = DEFAULT_SCREENSHOT_PROMPT
  rightClickAction.value = 'record'
  displayFontSize.value = 16
  displayLineHeight.value = 1.7
  systemPrompt.value = ''
  backgroundContext.value = ''
  backgroundMode.value = 'shared'
  selectedPromptTemplate.value = ''
  clearPromptTemplateAssociation()
  multiModelDisplayMode.value = DEFAULT_MULTI_MODEL_PREFERENCES.displayMode
  defaultDisplayModel.value = selectedModels.value[0] || ''
}
</script>

<style scoped>
.session-settings {
  width: 360px;
  height: 100vh;
  background: white;
  border-left: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
}

.settings-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid #e5e7eb;
  background: #f9fafb;
}

.settings-header .title {
  font-weight: 600;
  color: #1f2937;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
}

.display-control + .display-control {
  margin-top: 12px;
}

.display-control-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #4b5563;
  font-size: 13px;
  margin-bottom: 2px;
}

.display-control-header strong {
  color: #2563eb;
  font-variant-numeric: tabular-nums;
}

.display-preview {
  max-height: 180px;
  overflow: auto;
  padding: 12px;
  margin-top: 10px;
  border: 1px solid #dbeafe;
  border-radius: 10px;
  background: #f8fbff;
  color: #1f2937;
  overflow-wrap: anywhere;
}

.btn-close {
  color: #6b7280;
  font-size: 18px;
}

.settings-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  overflow-y: auto;
}

.settings-empty {
  padding: 24px;
  color: #9ca3af;
  text-align: center;
}

.section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.label {
  font-size: 13px;
  font-weight: 500;
  color: #374151;
  display: flex;
  align-items: center;
}

.label-with-tag {
  display: flex;
  align-items: center;
  gap: 8px;
}

.model-order-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
}

.model-tags-container {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  min-height: 60px;
}

.model-tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.model-tag-draggable {
  cursor: move;
  user-select: none;
  display: inline-flex !important;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  white-space: nowrap;
}

.model-tag-draggable :deep(.el-tag__content) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.drag-handle {
  cursor: grab;
  opacity: 0.6;
  font-size: 14px;
  line-height: 1;
  display: inline-flex;
  align-items: center;
}

.model-tag-draggable:active .drag-handle {
  cursor: grabbing;
}

.global-display-section {
  padding: 12px;
  border: 1px solid #dbeafe;
  border-radius: 10px;
  background: #eff6ff;
}

.reasoning-section {
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}

.reasoning-target {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.reasoning-model-name {
  min-width: 0;
  color: #475569;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.display-mode-group {
  width: 100%;
}

.display-mode-group :deep(.el-radio-button) {
  width: 50%;
}

.display-mode-group :deep(.el-radio-button__inner) {
  width: 100%;
}

.display-hint {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: #2563eb;
}

.actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 8px;
  padding-top: 16px;
  border-top: 1px solid #e5e7eb;
}

.action-button {
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.action-button .button-content {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  justify-content: center;
  height: 100%;
}

.action-button :deep(.el-button__text) {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.prompt-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #f59e0b;
  margin-top: 6px;
}

.neutral-hint {
  color: #64748b;
}

.template-snapshot {
  padding: 10px 12px;
  border: 1px solid #dbeafe;
  border-radius: 9px;
  background: #f8fbff;
  color: #475569;
  font-size: 12px;
  line-height: 1.55;
}

.template-snapshot > div:first-child {
  display: flex;
  align-items: center;
  gap: 7px;
}

.user-prompt-preview {
  margin-top: 7px;
  padding-top: 7px;
  border-top: 1px solid #e2e8f0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.background-mode-group {
  width: 100%;
}

.background-mode-group :deep(.el-radio-button) {
  width: 33.333%;
}

.background-mode-group :deep(.el-radio-button__inner) {
  width: 100%;
  padding-left: 8px;
  padding-right: 8px;
}

.shared-background-warning,
.background-disabled-hint {
  padding: 10px 12px;
  border-radius: 9px;
  font-size: 12px;
  line-height: 1.55;
}

.shared-background-warning {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  border: 1px solid #fde68a;
  background: #fffbeb;
  color: #b45309;
}

.background-disabled-hint {
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #64748b;
}

.save-status {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid #bbf7d0;
  border-radius: 10px;
  background: #f0fdf4;
  color: #166534;
  font-size: 12px;
  line-height: 1.55;
}

.save-status.dirty {
  border-color: #fed7aa;
  background: #fff7ed;
  color: #c2410c;
}

.save-status div {
  display: flex;
  flex-direction: column;
}

.save-status strong {
  font-size: 13px;
}
</style>
