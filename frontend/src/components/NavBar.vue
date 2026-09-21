<template>
  <nav class="navbar">
    <div class="navbar-content">
      <div class="flex items-center gap-3">
        <h1 class="text-xl font-semibold text-gray-800">💬 ChatGPT Web</h1>
      </div>
      <div class="flex gap-2">
        <el-button @click="$emit('open-prompt-lab')" :icon="DataAnalysis" type="primary" plain>
          八股实验室
        </el-button>
        <el-button 
          @click="$emit('open-session-settings')"
          :icon="Setting"
        >
          会话设置
        </el-button>
        <el-button 
          @click="$emit('clear-chat')"
          :icon="Delete"
          type="danger"
          plain
        >
          清空
        </el-button>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { Setting, Delete, DataAnalysis } from '@element-plus/icons-vue'

defineProps({
  config: {
    type: Object,
    default: () => ({ current_source: '', current_model: '' })
  }
})

defineEmits(['open-prompt-lab', 'open-session-settings', 'clear-chat'])
</script>

<style scoped>
.navbar {
  background: white;
  border-bottom: 1px solid #e8edf4;
  padding: 11px 20px;
  width: 100%;
  flex-shrink: 0;
  box-shadow: 0 1px 2px rgba(15, 23, 42, .03);
}

.navbar-content {
  max-width: 1280px;
  width: 100%;
  margin: 0 auto;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.navbar-content h1 { letter-spacing: -.02em; }
.navbar-content :deep(.el-button) { min-height: 38px; border-radius: 9px; }

@media (max-width: 720px) {
  .navbar { padding: 9px 10px; }
  .navbar-content { padding: 0; gap: 8px; }
  .navbar-content h1 { font-size: 16px; }
  .navbar-content :deep(.el-button) { padding: 8px 10px; }
}
</style>
