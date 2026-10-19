<template>
  <section class="scene-bar" aria-label="提示词场景">
    <div class="scene-buttons">
      <SceneButton :scene="{ id: 'default', name: '默认', description: '会话系统提示词' }"
        :selected="selectedId === null" :disabled="disabled" @select="selectScene(null)" />
      <SceneButton v-for="scene in catalog.scenes" :key="scene.id" :scene="scene"
        :selected="selectedId === scene.id" :disabled="disabled"
        @select="selectScene(scene)" />
      <button type="button" class="quiet" :disabled="disabled || busy" @click="openEditor" :title="loadError || '管理场景和切换选项'">{{ loadError ? '场景不可用 · 重试' : '＋ 管理场景' }}</button>
      <slot />
    </div>
    <el-dialog v-model="editing" title="提示词场景" top="6vh" width="min(720px, 94vw)" :close-on-click-modal="false">
    <div class="scene-status">
      <span>当前：{{ session?.session_config?.active_scene?.name || '默认' }}</span>
      <label><input type="checkbox" v-model="rerun" @change="savePreference" />切换后重答上一题</label>
      <button class="quiet" :disabled="disabled || busy || !session?.session_config?.active_scene" @click="selectScene(null)">恢复默认</button>
      <button class="quiet" @click="resetPositions">按钮归位</button>
    </div>
      <p>系统提示词与会话设置共用。当前场景的要求和项目资料追加到系统提示词末尾，不放入用户问题、不随历史轮数叠加。保存后立即应用。</p>
      <label class="field">系统提示词（与会话设置同步）<textarea v-model="draft.common_rules" rows="3" maxlength="30000" /></label>
      <div class="editor-scenes">
        <button v-for="(scene, index) in draft.scenes" :key="scene.id" class="quiet" :class="{ active: editIndex === index }" @click="editIndex = index">{{ scene.name || '未命名' }}</button>
        <button class="quiet" :disabled="draft.scenes.length >= 100" @click="addScene">＋ 新场景</button>
      </div>
      <template v-if="editedScene">
        <label class="field"><span><input type="checkbox" v-model="editedScene.use_scene_rules_as_system" style="width:auto" /> 此场景单独使用下方规则，不沿用会话系统提示词</span></label>
        <label class="field">按钮名称<input v-model="editedScene.name" maxlength="40" placeholder="例如：订单项目" /></label>
        <label class="field">场景提示词<textarea v-model="editedScene.rules" rows="4" maxlength="30000" placeholder="这个场景下，希望 AI 如何回答" /></label>
        <label class="field">项目资料（追加到系统提示词末尾）<textarea v-model="editedScene.background" rows="7" maxlength="100000" placeholder="粘贴这个项目的背景、职责、技术方案与成果；通用场景可留空" /></label>
        <button class="quiet danger" @click="removeScene">删除此场景</button>
      </template>
      <template #footer><button class="quiet" @click="editing = false">取消</button><el-button type="primary" :loading="saving" @click="saveCatalog">保存场景</el-button></template>
    </el-dialog>
  </section>
</template>
<script setup>
import { userStorage } from '../utils/auth'

import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../utils/api'
import SceneButton from './SceneButton.vue'
const props = defineProps({ session: Object, disabled: Boolean })
const emit = defineEmits(['selected'])
const pendingSelection = ref(null)
const selectedId = computed(() => pendingSelection.value ? pendingSelection.value.id : (props.session?.session_config?.active_scene?.id || null))
const catalog = ref({ common_rules: '', scenes: [] })
const draft = ref({ common_rules: '', scenes: [] })
const loadError = ref('')
const editing = ref(false), saving = ref(false), busy = ref(false), rerun = ref(true), editIndex = ref(0)
const editedScene = computed(() => draft.value.scenes[editIndex.value])
function savePreference() { try { userStorage.setItem('scene-rerun', JSON.stringify(rerun.value)) } catch {} }
function resetPositions() { window.dispatchEvent(new Event('reset-scene-positions')) }
async function load() {
  try {
    const result = await api.get('/prompt-scenes')
    if (!Array.isArray(result.scenes)) throw new Error('场景接口返回格式异常，请重启后端')
    catalog.value = result; loadError.value = ''
  } catch (error) {
    loadError.value = error.response?.status === 404
      ? '后端尚未加载场景接口，请重启后端服务后重试'
      : (error.response?.data?.detail || error.message || '无法连接场景服务')
    throw error
  }
}
onMounted(async () => {
  try { rerun.value = userStorage.getItem('scene-rerun') !== 'false' } catch {}
  try { await load() } catch { ElMessage.error(loadError.value) }
})
async function openEditor() {
  try { await load(); draft.value = JSON.parse(JSON.stringify(catalog.value)); draft.value.common_rules = props.session?.session_config?.system_prompt ?? props.session?.system_prompt ?? ''; editIndex.value = 0; editing.value = true }
  catch { ElMessage.error(loadError.value) }
}
function addScene() { draft.value.scenes.push({ id: crypto.randomUUID(), name: '', description: '', rules: '', background: '' }); editIndex.value = draft.value.scenes.length - 1 }
function removeScene() { draft.value.scenes.splice(editIndex.value, 1); editIndex.value = Math.max(0, editIndex.value - 1) }
async function saveCatalog() {
  if (draft.value.scenes.some(scene => !scene.name.trim())) return ElMessage.warning('请填写每个按钮的名称')
  saving.value = true
  try {
    catalog.value = await api.put('/prompt-scenes', draft.value)
    const activeId = props.session?.session_config?.active_scene?.id
    const active = catalog.value.scenes.find(scene => scene.id === activeId) || null
    selectScene(active, true, draft.value.common_rules, false)
    editing.value = false
    ElMessage.success('场景已保存，正在同步当前会话提示词')
  }
  catch { ElMessage.error('场景保存失败') }
  finally { saving.value = false }
}
function selectScene(scene, force = false, commonRules, shouldRerun = rerun.value) {
  if (props.disabled || !props.session?.id) return
  const desired = !force && scene?.id === selectedId.value ? null : scene
  if (!force && !desired && selectedId.value === null) return
  const selection = { id: desired?.id || null, token: Symbol() }
  pendingSelection.value = selection
  emit('selected', {
    sessionId: props.session.id, scene: desired, commonRules, rerun: shouldRerun,
    onSettled: () => { if (pendingSelection.value?.token === selection.token) pendingSelection.value = null }
  })
}

</script>
<style scoped>
:deep(.el-dialog__body) { max-height:65vh; overflow-y:auto; }
.scene-bar { padding:0; width:100%; min-width:0; }
.scene-buttons,.scene-status,.editor-scenes { display:flex; flex-wrap:wrap; align-items:center; gap:8px; }
.scene-buttons { flex-wrap:nowrap; overflow-x:auto; scrollbar-width:thin; padding:2px 0; }
.scene-buttons > :deep(*) { flex-shrink:0; }
.scene-status { margin-top:7px; font-size:12px; color:#64748b; }
.scene-status label { display:flex; align-items:center; gap:4px; }
.quiet { padding:5px 8px; background:transparent; border:0; border-radius:6px; color:#64748b; cursor:pointer; }
.quiet:hover,.quiet.active { background:#eef2ff; color:#4338ca; }
.quiet:disabled { opacity:.45; cursor:default; }
.field { display:flex; flex-direction:column; gap:6px; margin:14px 0; color:#475569; }
.field input,.field textarea { border:1px solid #cbd5e1; border-radius:8px; padding:9px; font:inherit; width:100%; box-sizing:border-box; }
.field textarea { resize:vertical; }
.danger { color:#dc2626; }
</style>
