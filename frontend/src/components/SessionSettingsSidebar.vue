<template>
  <div class="session-settings">
    <div class="settings-header">
      <div class="title">
        <el-icon><Setting /></el-icon>
        会话设置
      </div>
      <el-button text @click="$emit('close')" class="btn-close">
        <el-icon><Close /></el-icon>
      </el-button>
    </div>

    <div v-if="!session" class="settings-empty">
      请选择一个会话
    </div>

    <div v-else class="settings-body">
      <div class="section">
        <label class="label">配置源</label>
        <el-select v-model="selectedSource" @change="handleSourceChange" placeholder="选择配置源" style="width: 100%">
          <el-option v-for="source in config.sources" :key="source.name" :label="source.name" :value="source.name" />
        </el-select>
      </div>

      <div class="section">
        <div class="label-with-tag">
          <label class="label">模型选择</label>
          <el-tag size="small" type="info">支持多选并行</el-tag>
        </div>
        <el-select 
          v-model="selectedModels" 
          multiple 
          collapse-tags
          collapse-tags-tooltip
          placeholder="选择一个或多个模型" 
          style="width: 100%"
        >
          <el-option 
            v-for="model in currentSourceModels" 
            :key="model" 
            :label="model" 
            :value="model" 
          />
        </el-select>
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
            item-key="id"
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
                {{ element }}
              </el-tag>
            </template>
          </draggable>
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
        <div class="label-with-tag">
          <label class="label">系统提示词</label>
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
            v-for="template in promptTemplates" 
            :key="template.name" 
            :label="template.name" 
            :value="template.name" 
          />
          <el-option label="自定义..." value="custom" />
        </el-select>
        <el-input
          v-model="systemPrompt"
          type="textarea"
          :rows="4"
          placeholder="输入自定义系统提示词（可选）&#10;&#10;例如：你是一个专业的编程助手，擅长解答技术问题..."
          style="width: 100%"
        />
        <div class="prompt-hint">
          <el-icon><InfoFilled /></el-icon>
          系统提示词会影响AI的回答风格和角色设定
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
import { ref, computed, watch } from 'vue'
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

const emit = defineEmits(['close', 'updated'])

const selectedSource = ref('')
const selectedModels = ref([])  // 改为数组支持多选
const temperature = ref(0.7)
const topP = ref(1)
const saving = ref(false)
const systemPrompt = ref('')
const selectedPromptTemplate = ref('')

// 预设系统提示词模板
const promptTemplates = ref([
  {
    name: '默认助手',
    content: '你是一个友好、专业的AI助手，能够回答各种问题并提供帮助。'
  },
  {
    name: '面试准备助手',
    content: `你是一个参与过讯飞实习的研二同学，能够回答在讯飞实习的各种细节以及计算机测试开发的相关知识。
    下面的内容包含三部分，第一部分是我在讯飞实习的部分，第二部分是我个人在学校里面做的一个小项目潮人探店的内容，第三部分是面试官可能针对这些内容进行的提问以及对应的回答。以下是你回答的格式要求：
● 分点总结先行（核心摘要区）：
  ○ 在回答的最开头，必须使用列表（1, 2, 3...）给出总体的核心要点总结。
  ○ 特别要求： 列表中的内容必须是逻辑完整、表达精准的“总结性长句”，严禁使用“断层”的关键词（如“JMeter压测”、“Redis缓存”等）。每一个分点都应该是一句能够独立支撑论点的技术结论或方案概述，让我能通过读列表就快速抓到回答的精髓。
● 详细讲解随其后（技术深挖区）：
  ○ 在列表下方，针对每一个总结点，结合我提供的资料进行深入的细节讲解、原理说明和案例复盘。
  ○ 回答要体现技术深度（如：BIO/NIO的区别、Lua脚本的原子性、JMeter的Stripped模式等）。
● 开放性问题处理：
  ○ 针对“收获”、“挑战”、“选型理由”等开放性问题，请提供 4-5个不同的切入点，每个点都遵循上述“总结句+详细讲解”的格式，方便我根据实际面试情况进行筛选。
● 资料对齐与参考：
  ○ 如果是第三部分中已有的问题，请务必参考其中的答案逻辑，并结合前两部分的技术细节进行升华，不要脱离我提供的背景资料。
● 角色辨别：
  ○ 请分辨对话中哪些是面试官的提问。回答时语气要专业、自信，符合测试开发工程师的职业身份。`
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

const currentSourceModels = computed(() => {
  const source = props.config.sources?.find(s => s.name === selectedSource.value)
  return source ? source.models : []
})

function initFromSession() {
  if (!props.session || !props.config) return
  const sessionConfig = props.session.session_config
  if (sessionConfig) {
    selectedSource.value = sessionConfig.source_name || props.config.current_source
    // 支持新旧格式：models 数组或单个 model
    if (sessionConfig.models && sessionConfig.models.length > 0) {
      selectedModels.value = [...sessionConfig.models]
    } else if (sessionConfig.model) {
      selectedModels.value = [sessionConfig.model]
    } else {
      selectedModels.value = [props.config.current_model]
    }
    temperature.value = sessionConfig.temperature ?? 0.7
    topP.value = sessionConfig.top_p ?? 1
    systemPrompt.value = sessionConfig.system_prompt || ''
    
    // 检查是否匹配某个模板
    selectedPromptTemplate.value = ''
    if (systemPrompt.value) {
      const matchedTemplate = promptTemplates.value.find(t => t.content === systemPrompt.value)
      if (matchedTemplate) {
        selectedPromptTemplate.value = matchedTemplate.name
      } else {
        selectedPromptTemplate.value = 'custom'
      }
    }
  } else {
    selectedSource.value = props.config.current_source
    selectedModels.value = [props.config.current_model]
    temperature.value = 0.7
    topP.value = 1
    systemPrompt.value = ''
    selectedPromptTemplate.value = ''
  }
}

watch(() => [props.session, props.config], initFromSession, { deep: true, immediate: true })

function handleSourceChange() {
  const source = props.config.sources.find(s => s.name === selectedSource.value)
  if (source && source.models.length > 0) {
    // 切换配置源时，只保留第一个模型
    selectedModels.value = [source.models[0]]
  }
}

function removeModel(index) {
  if (selectedModels.value.length > 1) {
    selectedModels.value.splice(index, 1)
  } else {
    ElMessage.warning('至少需要选择一个模型')
  }
}

function handlePromptTemplateChange() {
  if (selectedPromptTemplate.value === 'custom') {
    // 选择自定义，不改变当前内容
    return
  } else if (selectedPromptTemplate.value === '') {
    // 选择无
    systemPrompt.value = ''
  } else {
    // 选择模板
    const template = promptTemplates.value.find(t => t.name === selectedPromptTemplate.value)
    if (template) {
      systemPrompt.value = template.content
    }
  }
}

async function handleSave() {
  if (!props.session) return
  if (selectedModels.value.length === 0) {
    ElMessage.warning('请至少选择一个模型')
    return
  }
  
  saving.value = true
  try {
    const payload = {
      source_name: selectedSource.value,
      models: selectedModels.value,  // 发送模型数组
      temperature: Number(temperature.value),
      top_p: Number(topP.value),
      system_prompt: systemPrompt.value || null  // 发送系统提示词
    }
    const response = await api.put(`/sessions/${props.session.id}/config`, payload)
    if (response.success) {
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
  selectedModels.value = [props.config.current_model]
  temperature.value = 0.7
  topP.value = 1
  systemPrompt.value = ''
  selectedPromptTemplate.value = ''
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
</style>
