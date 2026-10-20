<template>
  <el-dialog :model-value="true" title="换模型对比" width="min(900px, 94vw)" top="5vh" class="model-comparison-dialog" append-to-body @close="$emit('close')">
    <div class="comparison" @keydown.stop>
      <p>复用当时实际发送的提示词、历史和图片；只更换目标模型与推理档位。结果单独保存，不影响原回答及后续历史。</p>
      <p v-if="error" role="alert" class="error">{{ error }}</p>
      <p v-if="loading">正在读取请求快照…</p>
      <el-alert v-else-if="!snapshots.length" title="这条消息没有原始请求快照，无法保证历史一致。此功能仅支持更新后实际发送或重新生成的请求；不会用当前设置猜测旧请求。" type="warning" :closable="false" />
      <template v-if="snapshots.length">
        <label>原始请求版本（并行模型可能有不同的历史截断）</label>
        <select aria-label="原始请求版本" v-model="snapshotId" @change="preview = null"><option v-for="s in snapshots" :key="s.id" :value="s.id">{{ stamp(s.created_at) }} · {{ s.source }} / {{ s.model }} · {{ s.message_count }} 条消息</option></select>
        <button class="link" @click="showPreview">{{ preview ? '收起原始请求' : '查看原始提示词与历史' }}</button>
        <pre v-if="preview" class="request-preview">{{ preview }}</pre>
        <label>目标模型</label>
        <div class="target-row">
          <select aria-label="目标模型" v-model="targetKey"><option value="" disabled>选择要对比的模型</option><option v-for="t in targets" :key="t.key" :value="t.key">{{ t.key === pinned ? '★ ' : '' }}{{ t.source_name }} / {{ t.model }}</option></select>
          <button :disabled="!targetKey" @click="pin">{{ targetKey && targetKey === pinned ? '已置顶' : '置顶此模型' }}</button>
        </div>
        <label>目标推理档位（支持范围取决于模型）</label>
        <select aria-label="目标推理档位" v-model="effort"><option v-for="value in ['none','minimal','low','medium','high','xhigh']" :key="value" :value="value">{{ value }}</option></select>
        <el-button type="primary" :disabled="!targetKey || !snapshotId || submitting" :loading="submitting" @click="submit">使用此快照对比</el-button>
        <p class="hint">置顶选择保存在当前账号的浏览器中。关闭窗口后任务继续，重新打开可查看结果。</p>
      </template>
      <h3>已保存的对比回答 · {{ results.length }}</h3>
      <button class="link" @click="refresh">刷新结果</button>
      <article v-for="result in results" :key="result.id">
        <strong>{{ result.target.source_name }} / {{ result.target.model }}</strong>
        <small>{{ stamp(result.created_at) }} · {{ result.target.reasoning_effort }} · {{ statusLabel(result.status) }}<span v-if="result.latency_ms"> · {{ (result.latency_ms / 1000).toFixed(1) }} 秒</span></small>
        <small>原始快照 {{ result.snapshot_id.slice(0, 8) }} · 历史校验 {{ result.messages_sha256.slice(0, 12) }}</small>
        <p v-if="result.error" class="error">{{ result.error }}</p>
        <details v-if="result.reasoning_content"><summary>推理内容</summary><pre>{{ result.reasoning_content }}</pre></details>
        <div class="answer" v-html="renderMarkdown(result.content || '')"></div>
        <button v-if="result.content" class="link" @click="copy(result.content)">复制回答</button>
      </article>
    </div>
  </el-dialog>
</template>
<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import api from '../utils/api'
import { userStorage } from '../utils/auth'
import { renderMarkdown } from '../utils/markdown'
const props = defineProps({ sessionId: String, messageId: String, sources: Array })
defineEmits(['close'])
const snapshots = ref([]), results = ref([]), snapshotId = ref(''), targetKey = ref(''), pinned = ref(''), effort = ref('none')
const error = ref(''), preview = ref(null), loading = ref(true), submitting = ref(false)
let timer, disposed = false
const endpoint = `/sessions/${encodeURIComponent(props.sessionId)}/messages/${encodeURIComponent(props.messageId)}/comparisons`
try { pinned.value = userStorage.getItem('comparisonPinnedModel') || ''; targetKey.value = pinned.value } catch {}
const targets = computed(() => (props.sources || []).flatMap(s => s.models.map(model => ({ key: JSON.stringify([s.name, model]), source_name: s.name, model }))).sort((a,b) => Number(b.key === pinned.value) - Number(a.key === pinned.value)))
function stamp(value) { return new Date(value * 1000).toLocaleString() }
function statusLabel(value) { return ({pending:'生成中', success:'已保存', error:'失败', interrupted:'已中断'})[value] || value }
function pin() { pinned.value = targetKey.value; try { userStorage.setItem('comparisonPinnedModel', pinned.value) } catch { error.value = '浏览器未允许保存置顶偏好' } }
async function refresh() {
  clearTimeout(timer)
  try {
    const data = await api.get(endpoint)
    if (disposed) return
    snapshots.value = data.snapshots; results.value = data.results
    if (!snapshotId.value) snapshotId.value = data.snapshots[0]?.id || ''
    error.value = ''
  } catch (e) { error.value = e.response?.data?.detail || '读取失败，请重试' }
  finally {
    loading.value = false
    if (!disposed && results.value.some(r => r.status === 'pending')) timer = setTimeout(refresh, 2000)
  }
}
async function showPreview() {
  if (preview.value) { preview.value = null; return }
  try {
    const requestedId = snapshotId.value
    const record = await api.get(`${endpoint}/snapshots/${requestedId}`)
    if (disposed || requestedId !== snapshotId.value) return
    preview.value = JSON.stringify(record.parameters, (key, value) => typeof value === 'string' && value.startsWith('data:image/') ? '[原始图片数据已完整保存，重放时原样发送]' : value, 2)
  } catch (e) { error.value = e.response?.data?.detail || '快照读取失败' }
}
async function submit() {
  const target = targets.value.find(t => t.key === targetKey.value)
  if (!target) { error.value = '请选择当前可用的模型'; return }
  submitting.value = true
  try {
    await api.post(endpoint, { snapshot_id: snapshotId.value, target: { source_name: target.source_name, model: target.model, reasoning_effort: effort.value } })
    await refresh()
  } catch (e) { error.value = e.response?.data?.detail || '提交失败，请重试' }
  finally { submitting.value = false }
}
async function copy(value) { try { await navigator.clipboard.writeText(value) } catch { error.value = '复制失败，请手动选择文本复制' } }
onMounted(refresh)
onUnmounted(() => { disposed = true; clearTimeout(timer) })
</script>
<style scoped>
.comparison { max-height: 72vh; overflow: auto; color: #475569; line-height: 1.7; font-size: 13px; }
p { margin: 0 0 14px; }
label { display: block; color: #25344a; font-weight: 600; margin: 14px 0 6px; }
select { width: 100%; border: 1px solid #dbe3ed; border-radius: 8px; padding: 9px; background: white; margin-bottom: 10px; }
.target-row { display: flex; align-items: baseline; gap: 12px; }.target-row select { flex: 1; min-width: 0; }.target-row button { white-space: nowrap; }
.link { color: #2563eb; margin: 8px 0; }.error { color: #b42318; }.hint, small { color: #64748b; font-size: 12px; }
h3 { margin-top: 24px; font-size: 16px; }article { border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px; margin: 12px 0; }small { display: block; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; background: #f8fafc; padding: 12px; }.request-preview { max-height: 300px; overflow: auto; }.answer { overflow-wrap: anywhere; margin-top: 14px; }.answer :deep(pre) { overflow: auto; }.answer :deep(p) { margin: 8px 0; }
</style>
