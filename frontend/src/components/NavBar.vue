<template>
  <nav class="navbar">
    <div class="navbar-content">
      <div class="conversation-heading">
        <h1>{{ title || '新对话' }}</h1>
      </div>
      <div class="nav-actions">
        <el-button @click="$emit('open-prompt-lab')" :icon="DataAnalysis" text title="提示词实验室" aria-label="提示词实验室">提示词实验室</el-button>
        <el-button @click="$emit('open-session-settings')" :icon="Setting">会话设置</el-button>
      </div>
    </div>
  </nav>
</template>
<script setup>
import { Setting, DataAnalysis } from '@element-plus/icons-vue'
defineProps({ title: String, config: Object })
defineEmits(['open-prompt-lab', 'open-session-settings'])
</script>
<style scoped>
.navbar { padding: 8px 36px; flex-shrink: 0; border-bottom: 1px solid var(--line); background: var(--paper); }
.navbar-content { display: flex; align-items: center; justify-content: space-between; gap: 20px; }
.conversation-heading { min-width: 0; }
h1 { font-size: 17px; font-weight: 600; margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.nav-actions { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.nav-actions :deep(.el-button + .el-button) { margin-left: 0; }
@media(max-width: 720px) { .navbar { padding: 12px 16px; } .nav-actions { gap: 0; } .nav-actions :deep(.el-button) { padding: 8px; } .eyebrow { display: none; } h1 { max-width: 140px; font-size: 14px; } }
</style>
