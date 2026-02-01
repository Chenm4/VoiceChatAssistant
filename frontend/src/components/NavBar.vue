<template>
  <nav class="navbar">
    <div class="navbar-content">
      <div class="flex items-center gap-3">
        <h1 class="text-xl font-semibold text-gray-800">💬 ChatGPT Web</h1>
      </div>
      <div class="flex gap-2">
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
import { Setting, Delete } from '@element-plus/icons-vue'

defineProps({
  config: {
    type: Object,
    default: () => ({ current_source: '', current_model: '' })
  }
})

defineEmits(['open-session-settings', 'clear-chat'])
</script>

<style scoped>
.navbar {
  background: white;
  border-bottom: 1px solid #e5e7eb;
  padding: 12px 16px;
  width: 100%;
  flex-shrink: 0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.navbar-content {
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
