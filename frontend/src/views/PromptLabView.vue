<template>
  <div class="lab-page">
    <header class="lab-header">
      <div>
        <div class="lab-title-row">
          <el-button text @click="$emit('back')">← 返回聊天</el-button>
          <h1>八股回答提示词实验室</h1>
        </div>
        <p>批量比较 Qwen 模型与提示词，找到真正适合现场口述、可以直接背的回答。</p>
      </div>
      <el-button @click="loadRuns" :loading="loadingRuns">刷新历史</el-button>
    </header>

    <main class="lab-layout" v-loading="loadingCatalog">
      <aside class="lab-config">
        <section class="panel">
          <h2>1. 实验配置</h2>
          <label class="field-label">实验名称</label>
          <el-input v-model="form.name" placeholder="例如：MySQL 提示词对比" />

          <label class="field-label">Qwen 配置源</label>
          <el-select v-model="form.source_name" style="width: 100%" @change="handleSourceChange">
            <el-option v-for="source in catalog.sources" :key="source.name" :label="source.name" :value="source.name" />
          </el-select>

          <label class="field-label">模型（可多选）</label>
          <el-checkbox-group v-model="form.models" class="vertical-checks">
            <el-checkbox v-for="model in availableModels" :key="model" :label="model">{{ model }}</el-checkbox>
          </el-checkbox-group>

          <div class="parameter-grid">
            <div>
              <label class="field-label">Temperature</label>
              <el-input-number v-model="form.temperature" :min="0" :max="2" :step="0.1" :precision="1" />
            </div>
            <div>
              <label class="field-label">并发数</label>
              <el-input-number v-model="form.max_concurrency" :min="1" :max="5" />
            </div>
          </div>
        </section>

        <section class="panel background-panel">
          <div class="panel-heading">
            <h2>2. 个人与项目背景资料</h2>
            <el-button text size="small" :loading="savingBackground" @click="saveBackground">保存背景资料</el-button>
          </div>
          <p class="background-help">
            这里保存候选人的真实经历，聊天会话和实验室共用。回答规则放在 System Prompt，当前题目单独作为 User Prompt 发送。
          </p>
          <el-input
            v-model="backgroundDraft"
            type="textarea"
            :rows="12"
            resize="vertical"
            placeholder="填写个人信息、实习经历、项目背景、本人职责和技术难点"
          />
        </section>

        <section class="panel">
          <div class="panel-heading">
            <h2>3. 回答规则模板</h2>
            <div>
              <el-button text size="small" @click="openNewPrompt">新增模板</el-button>
              <el-button text size="small" @click="toggleAllPrompts">{{ allPromptsSelected ? '取消全选' : '全选' }}</el-button>
            </div>
          </div>
          <el-checkbox-group v-model="form.prompt_ids" class="template-list">
            <div v-for="prompt in catalog.prompts" :key="prompt.id" class="template-option">
              <div class="template-option-header">
                <el-checkbox :label="prompt.id">{{ prompt.name }} <small>v{{ prompt.version || 1 }}</small></el-checkbox>
                <div>
                  <el-button text size="small" @click.stop="openPromptHistory(prompt)">版本</el-button>
                  <el-button text size="small" @click.stop="openEditPrompt(prompt)">编辑</el-button>
                </div>
              </div>
              <p>{{ prompt.description }}</p>
              <button type="button" class="template-toggle" @click="togglePromptContent(prompt.id)">
                {{ expandedPromptIds.has(prompt.id) ? '收起模板内容' : '查看完整模板内容' }}
                <span :class="{ expanded: expandedPromptIds.has(prompt.id) }">⌄</span>
              </button>
              <div v-if="expandedPromptIds.has(prompt.id)" class="template-content">
                <div class="prompt-block-title">System Prompt</div>
                <pre>{{ prompt.system_prompt }}</pre>
                <div class="prompt-block-title">User Prompt 模板</div>
                <pre>{{ prompt.user_prompt_template }}</pre>
                <div class="prompt-role-help">System Prompt 保存稳定的回答规则；User Prompt 只保存本次题目。</div>
              </div>
            </div>
          </el-checkbox-group>
        </section>

        <section class="panel question-panel">
          <div class="panel-heading">
            <h2>4. 批量题目</h2>
            <el-button text size="small" @click="toggleVisibleQuestions">{{ visibleQuestionsSelected ? '取消当前分类' : '选择当前分类' }}</el-button>
          </div>
          <el-select v-model="categoryFilter" style="width: 100%; margin-bottom: 10px">
            <el-option label="全部分类" value="all" />
            <el-option v-for="category in categories" :key="category" :label="category" :value="category" />
          </el-select>
          <div class="question-count">已选 {{ form.question_ids.length }} / {{ catalog.questions.length }} 题</div>
          <el-checkbox-group v-model="form.question_ids" class="question-list">
            <el-checkbox v-for="question in visibleQuestions" :key="question.id" :label="question.id">
              <span class="question-category">{{ question.category }}</span>
              {{ question.question }}
            </el-checkbox>
          </el-checkbox-group>
        </section>

        <section class="panel run-panel">
          <div class="matrix-count">将生成 <strong>{{ combinationCount }}</strong> 条回答</div>
          <el-button type="primary" size="large" style="width: 100%" :loading="starting" :disabled="combinationCount === 0 || combinationCount > 120" @click="startRun">
            开始批量实验
          </el-button>
          <p v-if="combinationCount > 120" class="limit-warning">单次最多 120 个组合，请减少题目、模板或模型。</p>
        </section>
      </aside>

      <section class="lab-results">
        <div class="history-bar panel">
          <div>
            <h2>实验结果</h2>
            <span v-if="activeRun">{{ activeRunSummary }}</span>
          </div>
          <el-select v-model="selectedRunId" placeholder="打开历史实验" clearable filterable style="width: 520px" @change="openRun">
            <el-option v-for="run in runs" :key="run.id" :label="runHistoryLabel(run)" :value="run.id" />
          </el-select>
        </div>

        <div v-if="activeRun" class="run-summary panel">
          <div class="summary-top">
            <div>
              <el-tag :type="runTagType(activeRun.status)">{{ runStatusText(activeRun.status) }}</el-tag>
              <span>{{ activeRun.completed }} / {{ activeRun.total }} 完成</span>
              <span v-if="activeRun.failed">{{ activeRun.failed }} 条失败</span>
            </div>
            <span>{{ activeRun.models?.join('、') }}</span>
          </div>
          <el-progress :percentage="progressPercentage" :status="activeRun.status === 'completed' ? 'success' : undefined" />
          <div class="latency-help">回答卡片中的时间是“模型请求耗时”：从开始发送请求到收到完整非流式响应，不含并发排队和本地 JSON 保存时间。</div>
        </div>

        <div v-if="activeRun" class="result-toolbar panel">
          <el-select v-model="resultFilters.model" clearable placeholder="全部模型">
            <el-option v-for="model in activeRun.models" :key="model" :label="model" :value="model" />
          </el-select>
          <el-select v-model="resultFilters.prompt" clearable placeholder="全部模板">
            <el-option v-for="prompt in selectedRunPrompts" :key="prompt.id" :label="prompt.name" :value="prompt.id" />
          </el-select>
          <el-select v-model="resultFilters.status" clearable placeholder="全部状态">
            <el-option label="已完成" value="completed" />
            <el-option label="失败" value="failed" />
            <el-option label="等待中" value="pending" />
          </el-select>
          <span>显示 {{ filteredResults.length }} 条 · {{ groupedResults.length }} 道题</span>
        </div>

        <div v-if="!activeRun" class="empty-state panel">
          <h2>还没有打开实验</h2>
          <p>左侧选择模型、提示词和题目后开始运行，或者从右上角打开历史实验。</p>
        </div>

        <div v-else-if="filteredResults.length === 0" class="empty-state panel">
          <h2>没有符合筛选条件的结果</h2>
          <p>可以清空模型、模板或状态筛选后再查看。</p>
        </div>

        <div class="result-groups">
          <section v-for="group in groupedResults" :key="group.key" class="question-result-group">
            <header class="question-group-header">
              <div>
                <span class="category-pill">{{ group.category }}</span>
                <h3>{{ group.question }}</h3>
              </div>
              <span class="group-result-count">
                {{ group.items.length === group.total ? `${group.total} 个结果` : `显示 ${group.items.length} / 共 ${group.total} 个结果` }}
              </span>
            </header>

            <div class="comparison-grid">
              <article v-for="item in group.items" :key="item.id" class="result-card">
                <div class="result-card-header">
                  <div class="result-identity">
                    <el-tag>{{ item.model }}</el-tag>
                    <el-tag type="info">{{ item.prompt_name }}</el-tag>
                  </div>
                  <el-tooltip v-if="item.latency_ms" content="从开始发送请求到收到完整非流式响应；不含并发排队和本地保存时间" placement="top">
                    <span class="result-stat">模型请求 {{ (item.latency_ms / 1000).toFixed(1) }}s · {{ item.char_count }}字</span>
                  </el-tooltip>
                </div>

                <div v-if="item.status === 'completed'" class="answer markdown-body" v-html="renderMarkdown(item.answer)"></div>
                <el-alert v-else-if="item.status === 'failed'" :title="item.error || '调用失败'" type="error" :closable="false" />
                <div v-else class="pending-answer">等待模型回答…</div>

                <el-collapse v-if="item.prompt_snapshot" class="request-details">
                  <el-collapse-item title="查看本次完整提示词与请求">
                    <div class="prompt-block">
                      <div class="prompt-block-title">System Prompt</div>
                      <pre>{{ item.prompt_snapshot.system_prompt }}</pre>
                    </div>
                    <div class="prompt-block">
                      <div class="prompt-block-title">User Prompt（已代入本题）</div>
                      <pre>{{ item.prompt_snapshot.rendered_user_prompt }}</pre>
                    </div>
                    <div class="request-parameters">
                      配置源：{{ item.source_name }} · Temperature：{{ item.parameters?.temperature }} · Top P：{{ item.parameters?.top_p }} · Thinking：关闭
                    </div>
                  </el-collapse-item>
                </el-collapse>

                <div v-if="item.status === 'completed'" class="review-row">
                  <div class="rating-box">
                    <span>真人口述感</span>
                    <el-rate v-model="item.rating" @change="saveReview(item)" />
                  </div>
                  <el-input v-model="item.note" placeholder="记录优缺点，例如：太长、模板味重、要点很好背" @blur="saveReview(item)" />
                  <el-button @click="copyAnswer(item.answer)">复制</el-button>
                </div>
              </article>
            </div>
          </section>
        </div>
      </section>
    </main>

    <el-dialog v-model="promptDialogVisible" :title="editingPromptId ? '编辑提示词模板' : '新增提示词模板'" width="760px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="模板名称" required>
          <el-input v-model="promptDraft.name" placeholder="例如：90 秒真人口述版" />
        </el-form-item>
        <el-form-item label="用途说明">
          <el-input v-model="promptDraft.description" placeholder="说明适合什么题型和回答长度" />
        </el-form-item>
        <el-form-item label="System Prompt" required>
          <el-input v-model="promptDraft.system_prompt" type="textarea" :rows="8" resize="vertical" />
        </el-form-item>
        <el-form-item label="User Prompt 模板" required>
          <el-input v-model="promptDraft.user_prompt_template" type="textarea" :rows="10" resize="vertical" />
          <div class="placeholder-tip">必须保留 <code v-pre>{{question}}</code>，运行时会替换为当前题目。</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="promptDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingPrompt" @click="savePrompt">保存模板</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="historyDialogVisible" :title="`${historyPromptName} · 版本历史`" width="760px">
      <div v-loading="loadingPromptHistory" class="version-list">
        <article v-for="(version, index) in promptVersions" :key="`${version.id}-${version.version}`" class="version-card">
          <div class="version-heading">
            <strong>v{{ version.version || 1 }}</strong>
            <el-tag v-if="index === 0" type="success" size="small">当前版本</el-tag>
            <span>{{ formatTime(version.updated_at || version.created_at) }}</span>
          </div>
          <p>{{ version.description }}</p>
          <details>
            <summary>查看此版本完整内容</summary>
            <div class="prompt-block-title">System Prompt</div>
            <pre>{{ version.system_prompt }}</pre>
            <div class="prompt-block-title">User Prompt 模板</div>
            <pre>{{ version.user_prompt_template }}</pre>
          </details>
        </article>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../utils/api'
import { renderMarkdown } from '../utils/markdown'

defineEmits(['back'])

const catalog = reactive({ prompts: [], questions: [], sources: [], background: {} })
const runs = ref([])
const activeRun = ref(null)
const selectedRunId = ref('')
const categoryFilter = ref('all')
const loadingCatalog = ref(false)
const loadingRuns = ref(false)
const starting = ref(false)
const promptDialogVisible = ref(false)
const savingPrompt = ref(false)
const savingBackground = ref(false)
const backgroundDraft = ref('')
const editingPromptId = ref('')
const historyDialogVisible = ref(false)
const loadingPromptHistory = ref(false)
const historyPromptName = ref('')
const promptVersions = ref([])
const expandedPromptIds = ref(new Set())
let pollTimer = null

const promptDraft = reactive({
  name: '',
  description: '',
  system_prompt: '',
  user_prompt_template: '',
})

const form = reactive({
  name: '',
  source_name: '',
  models: [],
  prompt_ids: ['spoken_keypoints'],
  question_ids: [],
  temperature: 0.5,
  top_p: 0.9,
  max_concurrency: 2,
})

const resultFilters = reactive({ model: '', prompt: '', status: '' })
const availableModels = computed(() => catalog.sources.find(item => item.name === form.source_name)?.models || [])
const categories = computed(() => [...new Set(catalog.questions.map(item => item.category))])
const visibleQuestions = computed(() => categoryFilter.value === 'all' ? catalog.questions : catalog.questions.filter(item => item.category === categoryFilter.value))
const combinationCount = computed(() => form.models.length * form.prompt_ids.length * form.question_ids.length)
const allPromptsSelected = computed(() => form.prompt_ids.length === catalog.prompts.length)
const visibleQuestionsSelected = computed(() => visibleQuestions.value.length > 0 && visibleQuestions.value.every(item => form.question_ids.includes(item.id)))
const progressPercentage = computed(() => activeRun.value?.total ? Math.round(activeRun.value.completed / activeRun.value.total * 100) : 0)
const activeRunSummary = computed(() => activeRun.value ? runSummaryLabel(activeRun.value) : '')
const selectedRunPrompts = computed(() => {
  const prompts = new Map()
  for (const item of activeRun.value?.items || []) {
    if (item.prompt_id && !prompts.has(item.prompt_id)) {
      prompts.set(item.prompt_id, { id: item.prompt_id, name: item.prompt_name || item.prompt_id })
    }
  }
  return [...prompts.values()]
})
const filteredResults = computed(() => (activeRun.value?.items || []).filter(item =>
  (!resultFilters.model || item.model === resultFilters.model) &&
  (!resultFilters.prompt || item.prompt_id === resultFilters.prompt) &&
  (!resultFilters.status || item.status === resultFilters.status)
))
const groupedResults = computed(() => {
  const allItems = activeRun.value?.items || []
  const totalByQuestion = new Map()
  for (const item of allItems) {
    const key = questionGroupKey(item)
    totalByQuestion.set(key, (totalByQuestion.get(key) || 0) + 1)
  }

  const groups = new Map()
  for (const item of filteredResults.value) {
    const key = questionGroupKey(item)
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        category: item.category,
        question: item.question,
        total: totalByQuestion.get(key) || 0,
        items: [],
      })
    }
    groups.get(key).items.push(item)
  }
  return [...groups.values()]
})

function questionGroupKey(item) {
  return item.question_id || `${item.category || ''}\u0000${item.question || ''}`
}

async function loadCatalog(resetSelections = true) {
  loadingCatalog.value = true
  try {
    const data = await api.get('/prompt-lab/catalog')
    Object.assign(catalog, data)
    backgroundDraft.value = catalog.background?.content || ''
    if (resetSelections && catalog.sources.length) {
      form.source_name = catalog.sources[0].name
      form.models = catalog.sources[0].models.slice(0, 2)
    }
    if (resetSelections) form.question_ids = catalog.questions.slice(0, 3).map(item => item.id)
  } catch (error) {
    ElMessage.error('加载实验配置失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    loadingCatalog.value = false
  }
}

async function saveBackground() {
  savingBackground.value = true
  try {
    const saved = await api.patch('/prompt-lab/background', { content: backgroundDraft.value })
    catalog.background = saved
    ElMessage.success('背景资料已保存，后续聊天模板和新实验都会使用')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || error.message)
  } finally {
    savingBackground.value = false
  }
}

function openNewPrompt() {
  editingPromptId.value = ''
  Object.assign(promptDraft, {
    name: '',
    description: '',
    system_prompt: '',
    user_prompt_template: '面试题：{{question}}\n\n请给出一段可以直接口述的回答。',
  })
  promptDialogVisible.value = true
}

function openEditPrompt(prompt) {
  editingPromptId.value = prompt.id
  Object.assign(promptDraft, {
    name: prompt.name,
    description: prompt.description || '',
    system_prompt: prompt.system_prompt,
    user_prompt_template: prompt.user_prompt_template,
  })
  promptDialogVisible.value = true
}

async function openPromptHistory(prompt) {
  historyPromptName.value = prompt.name
  promptVersions.value = []
  historyDialogVisible.value = true
  loadingPromptHistory.value = true
  try {
    promptVersions.value = (await api.get(`/prompt-lab/prompts/${prompt.id}/history`)).versions || []
  } catch (error) {
    ElMessage.error('加载提示词版本失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    loadingPromptHistory.value = false
  }
}

async function savePrompt() {
  if (!promptDraft.name.trim() || !promptDraft.system_prompt.trim() || !promptDraft.user_prompt_template.trim()) {
    ElMessage.warning('请填写名称、System Prompt 和 User Prompt')
    return
  }
  if (!promptDraft.user_prompt_template.includes('{{question}}')) {
    ElMessage.warning('User Prompt 必须包含 {{question}} 占位符')
    return
  }
  savingPrompt.value = true
  try {
    const payload = { ...promptDraft }
    const saved = editingPromptId.value
      ? await api.patch(`/prompt-lab/prompts/${editingPromptId.value}`, payload)
      : await api.post('/prompt-lab/prompts', payload)
    await loadCatalog(false)
    if (!form.prompt_ids.includes(saved.id)) form.prompt_ids.push(saved.id)
    promptDialogVisible.value = false
    ElMessage.success(editingPromptId.value ? `已保存为 v${saved.version}` : '提示词模板已新增')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || error.message)
  } finally {
    savingPrompt.value = false
  }
}

async function loadRuns() {
  loadingRuns.value = true
  try {
    runs.value = (await api.get('/prompt-lab/runs')).runs || []
  } finally {
    loadingRuns.value = false
  }
}

function handleSourceChange() {
  form.models = availableModels.value.slice(0, 2)
}

function toggleAllPrompts() {
  form.prompt_ids = allPromptsSelected.value ? [] : catalog.prompts.map(item => item.id)
}

function togglePromptContent(promptId) {
  const next = new Set(expandedPromptIds.value)
  if (next.has(promptId)) next.delete(promptId)
  else next.add(promptId)
  expandedPromptIds.value = next
}

function toggleVisibleQuestions() {
  const ids = visibleQuestions.value.map(item => item.id)
  if (visibleQuestionsSelected.value) {
    form.question_ids = form.question_ids.filter(id => !ids.includes(id))
  } else {
    form.question_ids = [...new Set([...form.question_ids, ...ids])]
  }
}

async function startRun() {
  starting.value = true
  try {
    const run = await api.post('/prompt-lab/runs', { ...form })
    resetResultFilters()
    activeRun.value = run
    selectedRunId.value = run.id
    ElMessage.success(`实验已启动，共 ${run.total} 条回答`)
    await loadRuns()
    startPolling()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || error.message)
  } finally {
    starting.value = false
  }
}

async function openRun(runId) {
  if (!runId) return
  try {
    resetResultFilters()
    activeRun.value = await api.get(`/prompt-lab/runs/${runId}`)
    if (activeRun.value.status === 'running') startPolling()
    else stopPolling()
  } catch (error) {
    ElMessage.error('打开实验失败: ' + error.message)
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    if (!activeRun.value?.id) return
    try {
      const latest = await api.get(`/prompt-lab/runs/${activeRun.value.id}`)
      activeRun.value = latest
      if (latest.status !== 'running') {
        stopPolling()
        loadRuns()
        ElMessage.success('批量实验已完成')
      }
    } catch (error) {
      console.error('刷新实验进度失败:', error)
    }
  }, 2000)
}

function stopPolling() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = null
}

function resetResultFilters() {
  Object.assign(resultFilters, { model: '', prompt: '', status: '' })
}

async function saveReview(item) {
  if (!activeRun.value) return
  try {
    await api.patch(`/prompt-lab/runs/${activeRun.value.id}/items/${item.id}`, {
      rating: item.rating || null,
      note: item.note || '',
    })
  } catch (error) {
    ElMessage.error('保存评价失败: ' + error.message)
  }
}

async function copyAnswer(answer) {
  await navigator.clipboard.writeText(answer)
  ElMessage.success('已复制回答')
}

function formatTime(timestamp) {
  return timestamp ? new Date(timestamp * 1000).toLocaleString() : ''
}

function uniqueCount(run, field, itemField) {
  if (Array.isArray(run?.[field])) return new Set(run[field]).size
  return new Set((run?.items || []).map(item => item[itemField]).filter(Boolean)).size
}

function runQuestionCount(run) {
  return run.question_count ?? uniqueCount(run, 'question_ids', 'question_id')
}

function runPromptCount(run) {
  return run.prompt_count ?? uniqueCount(run, 'prompt_ids', 'prompt_id')
}

function runModelCount(run) {
  return run.model_count ?? uniqueCount(run, 'models', 'model')
}

function cleanRunName(run) {
  const name = String(run?.name || '').trim()
  return /^八股实验 \d{4}-\d{2}-\d{2}/.test(name) ? '' : name
}

function runSummaryLabel(run) {
  const customName = cleanRunName(run)
  return `${customName ? customName + ' · ' : ''}${runQuestionCount(run)}题 · ${runPromptCount(run)}模板 · ${runModelCount(run)}模型 · ${run.total || 0}回答`
}

function runHistoryLabel(run) {
  return `${formatTime(run.created_at)} · ${runSummaryLabel(run)}`
}

function runStatusText(status) {
  return ({ running: '运行中', completed: '已完成', completed_with_errors: '部分失败', interrupted: '已中断' })[status] || status
}

function runTagType(status) {
  return status === 'completed' ? 'success' : status === 'running' ? 'warning' : 'danger'
}

onMounted(async () => {
  await Promise.all([loadCatalog(), loadRuns()])
})
onBeforeUnmount(stopPolling)
</script>

<style scoped>
.lab-page { min-height: 100vh; background: #f4f6f9; color: #1f2937; }
.lab-header { height: 92px; padding: 16px 28px; display: flex; align-items: center; justify-content: space-between; background: white; border-bottom: 1px solid #e5e7eb; }
.lab-title-row { display: flex; align-items: center; gap: 12px; }
.lab-title-row h1 { margin: 0; font-size: 24px; font-weight: 700; }
.lab-header p { margin: 5px 0 0 92px; color: #64748b; font-size: 13px; }
.lab-layout { display: grid; grid-template-columns: 380px minmax(0, 1fr); height: calc(100vh - 92px); }
.lab-config { overflow-y: auto; padding: 16px; border-right: 1px solid #e5e7eb; }
.lab-results { overflow-y: auto; padding: 16px 22px 40px; }
.panel { background: white; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; margin-bottom: 14px; box-shadow: 0 1px 2px rgba(15, 23, 42, .04); }
.panel h2 { margin: 0; font-size: 16px; font-weight: 650; }
.panel-heading, .history-bar, .summary-top { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.background-help, .prompt-role-help { color: #64748b; font-size: 12px; line-height: 1.6; }
.background-help { margin: 9px 0 10px; }
.background-panel :deep(.el-alert) { margin-bottom: 10px; }
.prompt-role-help { margin-top: 8px; }
.field-label { display: block; margin: 14px 0 6px; color: #475569; font-size: 13px; font-weight: 600; }
.vertical-checks, .template-list { display: flex; flex-direction: column; align-items: stretch; gap: 5px; }
.template-option { padding: 10px; border: 1px solid #e5e7eb; border-radius: 9px; }
.template-option-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.template-option-header small { color: #94a3b8; font-weight: 400; }
.template-option > p { margin: 3px 0 7px 24px; color: #64748b; font-size: 12px; line-height: 1.45; }
.template-toggle { display: flex; align-items: center; gap: 5px; margin-left: 24px; padding: 2px 0; border: 0; background: transparent; color: #2563eb; font-size: 12px; cursor: pointer; }
.template-toggle span { display: inline-block; transition: transform .2s ease; }
.template-toggle span.expanded { transform: rotate(180deg); }
.template-content { margin: 8px 0 0 24px; color: #475569; font-size: 12px; }
.template-content pre { max-height: 220px; margin: 6px 0 10px; padding: 9px; overflow: auto; border-radius: 7px; background: #f8fafc; font-family: inherit; line-height: 1.55; white-space: pre-wrap; word-break: break-word; }
.parameter-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.parameter-grid :deep(.el-input-number) { width: 100%; }
.question-count { margin-bottom: 7px; color: #64748b; font-size: 12px; }
.question-list { max-height: 310px; overflow-y: auto; display: flex; flex-direction: column; align-items: stretch; gap: 7px; }
.question-list :deep(.el-checkbox) { height: auto; margin-right: 0; align-items: flex-start; white-space: normal; }
.question-list :deep(.el-checkbox__label) { line-height: 1.45; white-space: normal; }
.question-category, .category-pill { display: inline-block; padding: 1px 6px; margin-right: 5px; border-radius: 5px; background: #eef2ff; color: #4f46e5; font-size: 11px; }
.matrix-count { margin-bottom: 10px; text-align: center; color: #475569; }
.matrix-count strong { color: #2563eb; font-size: 20px; }
.limit-warning { color: #dc2626; font-size: 12px; }
.history-bar h2 { margin-bottom: 5px; }
.history-bar span { color: #64748b; font-size: 13px; }
.run-summary .summary-top { margin-bottom: 12px; }
.latency-help { margin-top: 9px; color: #64748b; font-size: 12px; }
.summary-top > div { display: flex; align-items: center; gap: 12px; }
.result-toolbar { display: flex; align-items: center; gap: 10px; }
.result-toolbar :deep(.el-select) { width: 190px; }
.result-toolbar > span { margin-left: auto; color: #64748b; font-size: 13px; }
.empty-state { padding: 70px 20px; text-align: center; color: #64748b; }
.result-groups { display: flex; flex-direction: column; gap: 18px; }
.question-result-group { min-width: 0; padding: 18px; background: #fff; border: 1px solid #dbe3ee; border-radius: 16px; box-shadow: 0 2px 10px rgba(15, 23, 42, .05); }
.question-group-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; padding: 0 2px 15px; }
.question-group-header h3 { margin: 8px 0 0; font-size: 17px; line-height: 1.55; }
.group-result-count { flex: none; padding: 5px 9px; border-radius: 999px; background: #eff6ff; color: #2563eb; font-size: 12px; white-space: nowrap; }
.comparison-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr)); align-items: start; gap: 14px; }
.result-card { min-width: 0; padding: 16px; background: #fbfcfe; border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 1px 4px rgba(15, 23, 42, .04); }
.result-card-header { display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 12px; min-height: 30px; padding-bottom: 12px; border-bottom: 1px solid #eef2f7; }
.result-identity { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; min-width: 0; }
.result-stat { display: block; flex: none; color: #64748b; font-size: 12px; white-space: nowrap; }
.answer { padding: 16px 4px; font-size: 16px; line-height: 1.8; }
.pending-answer { padding: 28px; text-align: center; color: #94a3b8; }
.request-details { margin: 2px 0 12px; }
.prompt-block { margin: 10px 0; }
.prompt-block-title { margin-bottom: 6px; color: #475569; font-size: 12px; font-weight: 700; }
.prompt-block pre { margin: 0; padding: 12px; overflow-x: auto; border-radius: 8px; background: #f8fafc; color: #334155; font-family: inherit; font-size: 13px; line-height: 1.65; white-space: pre-wrap; word-break: break-word; }
.request-parameters { color: #64748b; font-size: 12px; }
.review-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 10px; padding-top: 12px; border-top: 1px solid #eef2f7; }
.rating-box { grid-column: 1 / -1; display: flex; align-items: center; gap: 8px; color: #64748b; font-size: 12px; }
.placeholder-tip { margin-top: 6px; color: #64748b; font-size: 12px; }
.version-list { min-height: 100px; }
.version-card { padding: 14px; margin-bottom: 12px; border: 1px solid #e5e7eb; border-radius: 10px; }
.version-heading { display: flex; align-items: center; gap: 8px; }
.version-heading > span { margin-left: auto; color: #94a3b8; font-size: 12px; }
.version-card > p { color: #64748b; font-size: 13px; }
.version-card summary { cursor: pointer; color: #2563eb; font-size: 13px; }
.version-card pre { max-height: 260px; padding: 10px; overflow: auto; border-radius: 8px; background: #f8fafc; font-family: inherit; line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
@media (min-width: 1760px) { .comparison-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 1280px) {
  .lab-layout { display: block; height: auto; }
  .lab-config { overflow: visible; border-right: 0; border-bottom: 1px solid #e5e7eb; }
  .lab-results { overflow: visible; }
}
@media (max-width: 760px) {
  .lab-header { height: auto; padding: 14px 16px; align-items: flex-start; gap: 12px; }
  .lab-title-row { align-items: flex-start; }
  .lab-title-row h1 { font-size: 20px; }
  .lab-header p { margin-left: 0; }
  .lab-config, .lab-results { padding: 12px; }
  .history-bar, .question-group-header, .result-card-header { flex-direction: column; align-items: stretch; }
  .history-bar :deep(.el-select) { width: 100% !important; }
  .summary-top { align-items: flex-start; }
  .summary-top > div { align-items: flex-start; flex-wrap: wrap; }
  .result-toolbar { align-items: stretch; flex-direction: column; }
  .result-toolbar :deep(.el-select) { width: 100%; }
  .result-toolbar > span { margin-left: 0; }
  .question-result-group { padding: 14px; }
  .group-result-count { align-self: flex-start; }
  .result-stat { white-space: normal; }
}
</style>
