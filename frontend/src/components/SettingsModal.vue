<template>
  <div 
    class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
    @click.self="$emit('close')"
  >
    <div class="bg-white rounded-xl shadow-2xl max-w-2xl w-full mx-4 p-6 max-h-[90vh] overflow-y-auto">
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-xl font-semibold text-gray-800">
          <i class="fas fa-cog text-blue-600"></i> API 配置
        </h2>
        <button @click="$emit('close')" class="text-gray-400 hover:text-gray-600">
          <i class="fas fa-times text-xl"></i>
        </button>
      </div>
      
      <!-- 当前使用的配置 -->
      <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
        <h3 class="text-sm font-semibold text-blue-800 mb-3">
          <i class="fas fa-check-circle"></i> 当前配置
        </h3>
        
        <div class="space-y-3">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">配置源</label>
            <select 
              v-model="selectedSource"
              @change="onSourceChange"
              class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              <option v-for="source in localConfig.sources" :key="source.name" :value="source.name">
                {{ source.name }}
              </option>
            </select>
          </div>
          
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">模型</label>
            <select 
              v-model="selectedModel"
              class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              <option v-for="model in currentSourceModels" :key="model" :value="model">
                {{ model }}
              </option>
            </select>
          </div>
        </div>
        
        <button 
          @click="handleSwitch" 
          class="mt-4 w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
        >
          <i class="fas fa-sync-alt"></i> 切换配置
        </button>
      </div>
      
      <!-- 管理配置源 -->
      <div class="border border-gray-200 rounded-lg p-4">
        <h3 class="text-sm font-semibold text-gray-800 mb-4">
          <i class="fas fa-database"></i> 管理配置源
        </h3>
        
        <div class="space-y-4">
          <div 
            v-for="(source, index) in localConfig.sources" 
            :key="source.name"
            class="border border-gray-200 rounded-lg p-4 hover:border-blue-300 transition"
            :class="{ 'bg-blue-50 border-blue-300': source.name === selectedSource }"
          >
            <div class="flex items-center justify-between mb-3">
              <h4 class="font-semibold text-gray-800">
                {{ source.name }}
                <span v-if="source.name === selectedSource" class="ml-2 text-xs bg-blue-500 text-white px-2 py-1 rounded">
                  当前使用
                </span>
              </h4>
              <div class="flex gap-2">
                <button 
                  @click="toggleEdit(index)"
                  class="text-sm text-blue-600 hover:text-blue-800"
                >
                  <i :class="editingIndex === index ? 'fas fa-times' : 'fas fa-edit'"></i>
                  {{ editingIndex === index ? '取消' : '编辑' }}
                </button>
                <button 
                  @click="handleDeleteSource(source.name, index)"
                  class="text-sm text-red-600 hover:text-red-800"
                  :disabled="localConfig.sources.length === 1"
                  :class="{ 'opacity-50 cursor-not-allowed': localConfig.sources.length === 1 }"
                >
                  <i class="fas fa-trash"></i>
                  删除
                </button>
              </div>
            </div>
            
            <div v-if="editingIndex === index" class="space-y-3">
              <div>
                <label class="block text-xs font-medium text-gray-600 mb-1">API Key</label>
                <input 
                  type="password" 
                  v-model="source.api_key"
                  placeholder="sk-..."
                  class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
              </div>
              
              <div>
                <label class="block text-xs font-medium text-gray-600 mb-1">Base URL</label>
                <input 
                  type="text" 
                  v-model="source.base_url"
                  placeholder="https://api.openai.com/v1"
                  class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
              </div>
              
              <div>
                <label class="block text-xs font-medium text-gray-600 mb-1">模型列表（一行一个）</label>
                <textarea 
                  v-model="editingModelsText[index]"
                  @blur="updateModelsFromText(index)"
                  rows="4"
                  placeholder="按回车键换行输入多个模型，例如：&#10;gpt-4&#10;gpt-3.5-turbo&#10;claude-3-opus"
                  class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
                ></textarea>
              </div>
              
              <button 
                @click="handleUpdateSource(source)"
                class="w-full px-3 py-2 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 transition"
              >
                <i class="fas fa-save"></i> 保存修改
              </button>
            </div>
            
            <div v-else class="text-sm text-gray-600 space-y-1">
              <div>
                <i class="fas fa-key w-4"></i>
                API Key: {{ source.api_key ? '已配置 ✓' : '未配置 ✗' }}
              </div>
              <div>
                <i class="fas fa-link w-4"></i>
                {{ source.base_url }}
              </div>
              <div>
                <i class="fas fa-list w-4"></i>
                {{ source.models.length }} 个模型
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 新增配置源 -->
      <div class="border border-gray-200 rounded-lg p-4 mt-6">
        <h3 class="text-sm font-semibold text-gray-800 mb-4">
          <i class="fas fa-plus-circle"></i> 新增配置源
        </h3>
        <div class="space-y-3">
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">名称</label>
            <input 
              type="text" 
              v-model="newSource.name"
              placeholder="如：Gemini"
              class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">API Key</label>
            <input 
              type="password" 
              v-model="newSource.api_key"
              placeholder="sk-..."
              class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">Base URL</label>
            <input 
              type="text" 
              v-model="newSource.base_url"
              placeholder="https://api.example.com/v1"
              class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">模型列表（一行一个）</label>
            <textarea 
              v-model="newSource.modelsText"
              rows="4"
              placeholder="按回车键换行输入多个模型，例如：&#10;gpt-4&#10;gpt-3.5-turbo&#10;claude-3-opus"
              class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
            ></textarea>
          </div>
          <button 
            @click="handleAddSource"
            class="w-full px-3 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition"
          >
            <i class="fas fa-plus"></i> 新增配置
          </button>
        </div>
      </div>
      
      <div class="mt-6">
        <button 
          @click="$emit('close')" 
          class="w-full px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition"
        >
          关闭
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../utils/api'

const props = defineProps({
  config: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['close', 'refresh'])

const localConfig = ref({ ...props.config })
const selectedSource = ref(props.config.current_source)
const selectedModel = ref(props.config.current_model)
const editingIndex = ref(-1)
const editingModelsText = ref({}) // 存储每个配置源正在编辑的模型文本
const newSource = ref({
  name: '',
  api_key: '',
  base_url: '',
  modelsText: ''
})

watch(() => props.config, (newConfig) => {
  localConfig.value = { ...newConfig }
  selectedSource.value = newConfig.current_source
  selectedModel.value = newConfig.current_model
}, { deep: true })

const currentSourceModels = computed(() => {
  const source = localConfig.value.sources.find(s => s.name === selectedSource.value)
  return source ? source.models : []
})

function onSourceChange() {
  // 切换配置源时，自动选择该源的第一个模型
  const source = localConfig.value.sources.find(s => s.name === selectedSource.value)
  if (source && source.models.length > 0) {
    selectedModel.value = source.models[0]
  }
}

async function handleSwitch() {
  try {
    const response = await api.post('/config/switch', null, {
      params: {
        source_name: selectedSource.value,
        model: selectedModel.value
      }
    })
    
    if (response.success) {
      ElMessage.success(`已切换到 ${selectedSource.value} - ${selectedModel.value}`)
      emit('refresh')
    }
  } catch (error) {
    console.error('切换配置失败:', error)
    ElMessage.error('切换配置失败: ' + (error.response?.data?.detail || error.message))
  }
}

async function handleUpdateSource(source) {
  try {
    const response = await api.post('/config/update', source)
    
    if (response.success) {
      alert(`配置源 ${source.name} 已更新`)
      editingIndex.value = -1
      emit('refresh')
    }
  } catch (error) {
    console.error('更新配置源失败:', error)
    ElMessage.error('更新配置源失败: ' + (error.response?.data?.detail || error.message))
  }
}

async function handleAddSource() {
  const models = newSource.value.modelsText.split('\n').filter(m => m.trim())
  if (!newSource.value.name.trim() || models.length === 0) {
    ElMessage.warning('请填写配置源名称和模型列表')
    return
  }
  try {
    const payload = {
      name: newSource.value.name.trim(),
      api_key: newSource.value.api_key.trim(),
      base_url: newSource.value.base_url.trim(),
      models
    }
    const response = await api.post('/config/add', payload)
    if (response.success) {
      ElMessage.success(`配置源 ${payload.name} 已新增`)
      newSource.value = { name: '', api_key: '', base_url: '', modelsText: '' }
      emit('refresh')
    }
  } catch (error) {
    console.error('新增配置源失败:', error)
    ElMessage.error('新增配置源失败: ' + (error.response?.data?.detail || error.message))
  }
}

function toggleEdit(index) {
  if (editingIndex.value === index) {
    editingIndex.value = -1
  } else {
    editingIndex.value = index
    // 初始化编辑文本
    editingModelsText.value[index] = localConfig.value.sources[index].models.join('\n')
  }
}

function updateModels(index, event) {
  const text = event.target.value
  const models = text.split('\n').map(m => m.trim()).filter(m => m)
  localConfig.value.sources[index].models = models
}

function updateModelsFromText(index) {
  // 当失去焦点时，更新模型列表
  const text = editingModelsText.value[index] || ''
  const models = text.split('\n').map(m => m.trim()).filter(m => m)
  localConfig.value.sources[index].models = models
}

async function handleDeleteSource(sourceName, index) {
  if (localConfig.value.sources.length === 1) {
    ElMessage.warning('至少需要保留一个配置源')
    return
  }
  
  if (sourceName === selectedSource.value) {
    ElMessage.warning('不能删除当前正在使用的配置源，请先切换到其他配置源')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `确定要删除配置源 "${sourceName}" 吗？`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    // 用户取消
    return
  }
  
  try {
    const response = await api.delete(`/config/source/${encodeURIComponent(sourceName)}`)
    if (response.success) {
      // 通知父组件刷新全局配置
      emit('refresh')
      ElMessage.success(`配置源 ${sourceName} 已删除`)
    }
  } catch (error) {
    console.error('删除配置源失败:', error)
    ElMessage.error('删除配置源失败: ' + (error.response?.data?.detail || error.message))
  }
}
</script>
