<template>
  <div class="session-sidebar" :class="{ collapsed: isCollapsed }">
    <!-- 折叠按钮 - 细长按钮贴在右边缘 -->
    <button
      @click="toggleCollapse"
      class="collapse-btn"
      :class="{ collapsed: isCollapsed }"
      :title="isCollapsed ? '展开会话栏' : '收起会话栏'"
      :aria-label="isCollapsed ? '展开会话栏' : '收起会话栏'"
    >
      <AppIcon :name="isCollapsed ? 'chevron-right' : 'chevron-left'" class=""  />
    </button>

    <div v-if="!isCollapsed" class="sidebar-brand"><span class="brand-mark"><AudioLines :size="22" /></span><div><strong>轻语</strong><span>VOICE ASSISTANT</span></div></div>
    <button v-if="!isCollapsed" class="sidebar-lab" @click="emit('open-prompt-lab')">提示词实验室</button>
    <!-- 顶部工具栏 -->
    <div class="sidebar-header" v-if="!isCollapsed">
      <div class="header-buttons">
        <el-button 
          type="primary"
          @click="handleCreateSession" 
          :icon="Plus"
          style="flex: 1"
        >
          新建对话
        </el-button>

      </div>
    </div>

    <div v-if="!isCollapsed" class="sidebar-search" role="search">
      <Search :size="16" aria-hidden="true" />
      <input v-model="searchQuery" placeholder="搜索标题与内容" aria-label="搜索对话标题与内容" @keydown.esc="searchQuery = ''" />
      <LoaderCircle v-if="isSearching" :size="14" class="search-spinner" aria-label="正在搜索" />
      <button v-else-if="searchQuery" class="search-clear" aria-label="清除搜索" @click="searchQuery = ''"><X :size="14" /></button>
    </div>
    <div v-if="!isCollapsed" class="sidebar-section-label">{{ searchQuery.trim() ? '搜索结果' : '最近对话' }} <span>{{ searchQuery.trim() ? filteredSessions.length : sessions.length }}</span></div>
    <div v-if="!isCollapsed && searchQuery.trim()" class="search-status" role="status" aria-live="polite">
      <span v-if="isSearching">正在搜索全部对话…</span>
      <template v-else-if="searchFailures"><span>部分对话未能加载</span><button @click="runSearch">重试</button></template>
      <span v-else>已搜索标题和消息正文</span>
    </div>
    <!-- 会话列表容器 -->
    <div v-if="!isCollapsed" class="session-list-wrapper">
      <!-- 会话列表 -->
      <div class="session-list">
        <div
          v-for="session in filteredSessions"
          :key="session.id"
          class="session-item"
          :class="{ active: session.id === currentSessionId }"
          @click="handleSwitchSession(session.id)"
          role="button" tabindex="0" @keydown.enter.self="handleSwitchSession(session.id)" @keydown.space.self.prevent="handleSwitchSession(session.id)"
          :aria-current="session.id === currentSessionId ? 'true' : undefined"
        >
          <div class="session-content">
            <div v-if="editingSessionId === session.id" class="session-title-edit">
              <input
                ref="titleInput"
                v-model="editingTitle"
                @blur="handleSaveTitle(session.id)"
                @keyup.enter="handleSaveTitle(session.id)"
                @keyup.esc="cancelEdit"
                class="title-input"
                @click.stop
              >
            </div>
            <div v-else class="session-info">
              <div class="session-title" :title="session.title">{{ session.title }}</div>
              <p v-if="session.snippet" class="search-snippet"><span>内容 · </span><template v-for="(part, index) in highlightedSnippet(session.snippet)" :key="index"><mark v-if="part.match">{{ part.text }}</mark><template v-else>{{ part.text }}</template></template></p>
              <div class="session-meta">
                <span class="message-count">
                  {{ session.message_count ?? session.messages?.length ?? 0 }} 条消息
                </span>
                <span v-if="getAudioCount(session) > 0" class="audio-count">
                  {{ getAudioCount(session) }} 段录音
                </span>
                <span class="time" :title="formatTime(session.updated_at)">{{ formatShortTime(session.updated_at) }}</span>
              </div>
            </div>
          </div>

          <div class="session-actions" @click.stop>
            <el-button 
              text
              @click="handleEditTitle(session.id, session.title)" 
              :icon="Edit"
              size="small"
              title="重命名"
            />
            <el-dropdown
              trigger="click"
              @command="handleSessionAction(session.id, $event)"
            >
              <el-button
                text
                :icon="MoreFilled"
                size="small"
                title="会话导出"
                aria-label="会话导出"
              />
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="copy-user">复制全部发送消息</el-dropdown-item>
                  <el-dropdown-item command="copy-assistant">复制全部返回消息</el-dropdown-item>
                  <el-dropdown-item command="copy-all">复制全部消息</el-dropdown-item>
                  <el-dropdown-item
                    command="merge-audio"
                    divided
                    :disabled="getAudioCount(session) === 0"
                  >
                    合并并下载录音{{ getAudioCount(session) ? ` (${getAudioCount(session)})` : '' }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button 
              text
              @click="handleDeleteSession(session.id)" 
              :icon="Delete"
              size="small"
              type="danger"
              title="删除"
            />
          </div>
        </div>

        <div v-if="filteredSessions.length === 0 && !isSearching && !searchFailures" class="empty-state">
          <AppIcon name="comments" class="  text-4xl text-gray-300 mb-4" />
          <p class="text-gray-400">{{ searchQuery ? '没有找到匹配的对话' : '还没有对话，从这里开始' }}</p>
        </div>
      </div>
    </div>

    <div v-if="!isCollapsed" class="sidebar-footer"><el-button text :icon="Setting" @click="$emit('open-settings')">全局设置</el-button><span>让想法自然流动</span></div>
    <!-- 折叠状态下的按钮 -->
    <div v-if="isCollapsed" class="collapsed-actions">
      <el-button 
        type="primary"
        circle
        @click="handleCreateSession" 
        :icon="Plus"
        title="新建对话"
      />
      <el-button 
        circle
        @click="$emit('open-settings')"
        :icon="Setting"
        title="全局设置"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, computed, watch, onUnmounted } from 'vue'
import { AudioLines, Search, X, LoaderCircle } from 'lucide-vue-next'
import api from '../utils/api'
import { createSessionSearch } from '../utils/sessionSearch'
import { ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, Setting, MoreFilled } from '@element-plus/icons-vue'

const props = defineProps({
  sessions: {
    type: Array,
    default: () => []
  },
  currentSessionId: {
    type: String,
    default: null
  }
})

const emit = defineEmits([
  'open-prompt-lab',
  'create-session',
  'switch-session',
  'delete-session',
  'update-title',
  'open-settings',
  'copy-session',
  'merge-session-audio'
])

const isCollapsed = ref(window.innerWidth < 760)
const searchQuery = ref('')
const searchResults = ref([])
const isSearching = ref(false)
const searchFailures = ref(0)
const filteredSessions = computed(() => searchQuery.value.trim() ? searchResults.value : props.sessions)
const searchSessions = createSessionSearch((id, signal) => api.get(`/sessions/${id}`, { signal }))
let searchTimer
let searchController
let searchVersion = 0
async function runSearch() {
  clearTimeout(searchTimer)
  searchController?.abort()
  const version = ++searchVersion
  const query = searchQuery.value.trim()
  if (!query) { isSearching.value = false; searchResults.value = []; searchFailures.value = 0; return }
  searchController = new AbortController()
  isSearching.value = true
  searchFailures.value = 0
  const result = await searchSessions(props.sessions, query, searchController.signal)
  if (version !== searchVersion) return
  searchResults.value = result.matches
  searchFailures.value = result.failures
  isSearching.value = false
}
watch([searchQuery, () => props.sessions], () => {
  clearTimeout(searchTimer)
  searchController?.abort()
  searchVersion++
  searchResults.value = []
  searchFailures.value = 0
  isSearching.value = Boolean(searchQuery.value.trim())
  if (isSearching.value) searchTimer = setTimeout(runSearch, 250)
}, { deep: true })
onUnmounted(() => { clearTimeout(searchTimer); searchController?.abort(); searchVersion++ })
function highlightedSnippet(text) {
  const query = searchQuery.value.trim()
  const index = text.toLocaleLowerCase().indexOf(query.toLocaleLowerCase())
  if (!query || index < 0) return [{ text }]
  return [{ text: text.slice(0, index) }, { text: text.slice(index, index + query.length), match: true }, { text: text.slice(index + query.length) }]
}
function formatShortTime(timestamp) {
  const date = new Date(timestamp * 1000)
  return `${date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}
const editingSessionId = ref(null)
const editingTitle = ref('')
const titleInput = ref(null)

function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
}

function handleCreateSession() {
  emit('create-session')
}

function handleSwitchSession(sessionId) {
  if (editingSessionId.value) return
  emit('switch-session', sessionId)
}

function getAudioCount(session) {
  return session.audio_count ?? session.audio_files?.length ?? 0
}

function handleSessionAction(sessionId, command) {
  if (command === 'merge-audio') {
    emit('merge-session-audio', sessionId)
    return
  }
  emit('copy-session', sessionId, command)
}

function handleEditTitle(sessionId, currentTitle) {
  editingSessionId.value = sessionId
  editingTitle.value = currentTitle
  nextTick(() => {
    if (titleInput.value && titleInput.value[0]) {
      titleInput.value[0].focus()
      titleInput.value[0].select()
    }
  })
}

function handleSaveTitle(sessionId) {
  if (editingTitle.value.trim()) {
    emit('update-title', sessionId, editingTitle.value.trim())
  }
  editingSessionId.value = null
  editingTitle.value = ''
}

function cancelEdit() {
  editingSessionId.value = null
  editingTitle.value = ''
}

async function handleDeleteSession(sessionId) {
  try {
    await ElMessageBox.confirm(
      '确定要删除这个对话吗？',
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    emit('delete-session', sessionId)
  } catch {
    // 用户取消
  }
}

function formatTime(timestamp) {
  const date = new Date(timestamp * 1000)
  
  // 格式：2026-01-31 11:30:45
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}`
}
</script>

<style scoped>
.sidebar-lab { margin: 0 20px 8px; min-height: 34px; border: 1px solid #e4e4e4; border-radius: 8px; background: white; color: #555; cursor: pointer; }
.sidebar-lab:hover { background: #f0f0f0; }
.session-sidebar {
  width: 260px;
  height: 100vh;
  background: #f5f7fb;
  border-right: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
  overflow: hidden;
  position: relative;
}

.session-sidebar.collapsed {
  width: 72px;
}

/* 折叠按钮 - 贴在右边缘的细长按钮 */
.collapse-btn {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 24px;
  height: 64px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid #e5e7eb;
  border-right: none;
  border-radius: 4px 0 0 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  font-size: 11px;
  transition: all 0.2s;
  z-index: 10;
  box-shadow: -2px 0 4px rgba(0, 0, 0, 0.05);
}

.collapse-btn:hover {
  width: 28px;
  background: white;
  color: #3b82f6;
  box-shadow: -2px 0 8px rgba(0, 0, 0, 0.1);
}

.collapse-btn.collapsed {
  right: 0;
  left: auto;
  border-radius: 0 4px 4px 0;
  border-right: 1px solid #e5e7eb;
  border-left: none;
  box-shadow: 2px 0 4px rgba(0, 0, 0, 0.05);
}

.collapse-btn.collapsed:hover {
  width: 28px;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.1);
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #e5e7eb;
  background: white;
  flex-shrink: 0;
}

.header-buttons {
  display: flex;
  gap: 8px;
  align-items: center;
}

.session-list-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.session-item {
  position: relative;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s;
  display: block;
}

.session-item:hover {
  border-color: #667eea;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.1);
}

.session-item.active {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
  border-color: #667eea;
}

.session-content {
  min-width: 0;
  width: 100%;
}

.session-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.session-title {
  font-size: 14px;
  font-weight: 500;
  color: #1f2937;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 80px;
}

.session-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #9ca3af;
  white-space: nowrap;
  min-width: 0;
}

.message-count {
  flex-shrink: 0;
}

.audio-count {
  white-space: nowrap;
  flex-shrink: 0;
}

.time {
  margin-left: auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  font-variant-numeric: tabular-nums;
}

.session-title-edit {
  width: 100%;
}

.title-input {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid #667eea;
  border-radius: 4px;
  font-size: 14px;
  outline: none;
}

.session-actions {
  position: absolute;
  top: 7px;
  right: 7px;
  display: flex;
  gap: 0;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s;
}

.session-item:hover .session-actions,
.session-item:focus-within .session-actions {
  opacity: 1;
  pointer-events: auto;
}

.session-actions :deep(.el-button) {
  width: 28px;
  height: 28px;
  padding: 0;
  margin: 0;
}

@media (hover: none) {
  .session-actions {
    opacity: 1;
    pointer-events: auto;
  }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #9ca3af;
}

.collapsed-actions {
  padding: 20px 14px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.collapsed-actions :deep(.el-button) {
  width: 42px;
  height: 42px;
  margin: 0;
}

/* 滚动条样式 */
.session-list::-webkit-scrollbar {
  width: 6px;
}

.session-list::-webkit-scrollbar-track {
  background: transparent;
}

.session-list::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 3px;
}

.session-list::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}
</style>
