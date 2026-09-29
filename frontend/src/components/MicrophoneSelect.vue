<template>
  <div class="microphone-control">
    <label class="microphone-label">
      <span>麦克风</span>
      <select v-model="selectedIndex" :disabled="disabled || loading" aria-label="选择录音麦克风" :title="selectedName" @change="selectDevice">
        <option value="">系统默认{{ defaultName ? ` · ${defaultName}` : '' }}</option>
        <option v-for="device in devices" :key="device.index" :value="String(device.index)">{{ device.name }}</option>
      </select>
    </label>
    <button type="button" :disabled="disabled || loading" title="刷新麦克风列表" aria-label="刷新麦克风列表" @click="loadDevices">{{ loading ? '加载中' : '刷新' }}</button>
    <span v-if="error" class="microphone-error" role="status">{{ error }}</span>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../utils/api'

defineProps({ disabled: Boolean })
const emit = defineEmits(['change'])
const devices = ref([])
const selectedIndex = ref('')
const defaultIndex = ref(null)
const loading = ref(false)
const error = ref('')
const storageKey = 'recordingMicrophone'
const defaultName = computed(() => devices.value.find(device => device.index === defaultIndex.value)?.name || '')
const selectedName = computed(() => devices.value.find(device => String(device.index) === selectedIndex.value)?.name || '系统默认麦克风')

function selectDevice() {
  const device = devices.value.find(device => String(device.index) === selectedIndex.value) || null
  error.value = ''
  try { localStorage.setItem(storageKey, JSON.stringify(device)) } catch {}
  emit('change', device)
}

async function loadDevices() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    const result = await api.get('/recording/devices')
    devices.value = result.devices
    defaultIndex.value = result.default_index
    let saved = null
    try { saved = JSON.parse(localStorage.getItem(storageKey) || 'null') } catch {}
    const matching = saved && (devices.value.find(device => device.index === saved.index && device.name === saved.name)
      || devices.value.find(device => device.name === saved.name))
    selectedIndex.value = matching ? String(matching.index) : ''
    emit('change', matching || null)
    if (saved && !matching) error.value = '原麦克风已断开，已改为系统默认'
    else if (!devices.value.length) error.value = '未发现麦克风'
  } catch {
    error.value = '无法加载麦克风，请重试刷新'
  } finally {
    loading.value = false
  }
}

onMounted(loadDevices)
</script>

<style scoped>
.microphone-control, .microphone-label { display: flex; align-items: center; gap: 6px; }
.microphone-control { flex-wrap: wrap; color: #64748b; font-size: 12px; }
.microphone-label select { max-width: 210px; min-width: 100px; padding: 4px 6px; border: 1px solid #cbd5e1; border-radius: 6px; background: white; color: #334155; font: inherit; }
.microphone-control button { border: 0; background: transparent; color: #4f46e5; font: inherit; cursor: pointer; }
.microphone-control :disabled { opacity: .5; cursor: not-allowed; }
.microphone-error { color: #b45309; }
</style>
