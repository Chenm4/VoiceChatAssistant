<template>
  <div class="session-sidebar" :class="{ collapsed: isCollapsed }">
    <!-- 折叠按钮 - 细长按钮贴在右边缘 -->
    <button @click="toggleCollapse" class="collapse-btn" :class="{ collapsed: isCollapsed }">
      <i class="fas" :class="isCollapsed ? 'fa-chevron-right' : 'fa-chevron-left'"></i>
    </button>

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
        <el-button 
          @click="$emit('open-settings')"
          :icon="Setting"
          style="flex: 1"
        >
          全局设置
        </el-button>
      </div>
    </div>

    <!-- 会话列表容器 -->
    <div v-if="!isCollapsed" class="session-list-wrapper">
      <!-- 会话列表 -->
      <div class="session-list">
        <div
          v-for="session in sessions"
          :key="session.id"
          class="session-item"
          :class="{ active: session.id === currentSessionId }"
          @click="handleSwitchSession(session.id)"
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
              <div class="session-title">{{ session.title }}</div>
              <div class="session-meta">
                <span class="message-count">
                  {{ session.messages?.length || 0 }} 条消息
                </span>
                <span class="time">{{ formatTime(session.updated_at) }}</span>
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

        <div v-if="sessions.length === 0" class="empty-state">
          <i class="fas fa-comments text-4xl text-gray-300 mb-4"></i>
          <p class="text-gray-400">暂无对话</p>
        </div>
      </div>
    </div>

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
import { ref, nextTick, computed } from 'vue'
import { ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, Setting } from '@element-plus/icons-vue'

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
  'create-session',
  'switch-session',
  'delete-session',
  'update-title',
  'open-settings'
])

const isCollapsed = ref(false)
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
  const seconds = String(date.getSeconds()).padStart(2, '0')
  
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}
</script>

<style scoped>
.session-sidebar {
  width: 260px;
  height: 100vh;
  background: #f8f9fa;
  border-right: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
  overflow: hidden;
  position: relative;
}

.session-sidebar.collapsed {
  width: 60px;
}

/* 折叠按钮 - 贴在右边缘的细长按钮 */
.collapse-btn {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 12px;
  height: 60px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid #e5e7eb;
  border-right: none;
  border-radius: 4px 0 0 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  font-size: 10px;
  transition: all 0.2s;
  z-index: 10;
  box-shadow: -2px 0 4px rgba(0, 0, 0, 0.05);
}

.collapse-btn:hover {
  width: 16px;
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
  width: 16px;
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
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 8px;
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
  flex: 1;
  min-width: 0;
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
}

.session-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: #9ca3af;
}

.message-count {
  display: flex;
  align-items: center;
  gap: 4px;
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
  display: flex;
  gap: 0;
  opacity: 0;
  transition: opacity 0.2s;
}

.session-item:hover .session-actions {
  opacity: 1;
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
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  flex: 1;
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
