<template>
  <div class="microphone-control">
    <label class="microphone-label">
      <span>{{ label }}</span>
      <select v-model="selectedIndex" :disabled="disabled || loading" :aria-label="label + '设备'" :title="selectedName" @change="selectDevice">
        <option value="">{{ `系统默认${defaultName ? ' · ' + defaultName : ''}` }}</option>
        <option v-for="device in devices" :key="device.index" :value="String(device.index)">{{ device.name }}</option>
      </select>
    </label>
    <button type="button" :disabled="disabled || loading" title="刷新麦克风列表" :aria-label="'刷新' + label + '设备列表'" @click="loadDevices">{{ loading ? '加载中' : '刷新' }}</button>
    <span v-if="error" class="microphone-error" role="status">{{ error }}</span>
  </div>
</template>

<script setup>
import { userStorage } from '../utils/auth'

import { computed, onMounted, ref } from 'vue'
import api from '../utils/api'
import { preferredRecordingDevice } from '../utils/recordingDevices'

const props = defineProps({ disabled: Boolean, label: { type: String, default: '麦克风' },
  storageKey: { type: String, default: 'recordingMicrophone' }, preferUsb: Boolean, preferMicrophone: Boolean })
const emit = defineEmits(['change'])
const devices = ref([])
const selectedIndex = ref('')
const defaultIndex = ref(null)
const loading = ref(false)
const error = ref('')
const defaultName = computed(() => devices.value.find(device => device.index === defaultIndex.value)?.name || '')
const selectedName = computed(() => devices.value.find(device => String(device.index) === selectedIndex.value)?.name || '系统默认麦克风')

function selectDevice() {
  const device = devices.value.find(device => String(device.index) === selectedIndex.value) || null
  error.value = ''
  try { userStorage.setItem(props.storageKey, JSON.stringify(device)) } catch {}
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
    try { saved = JSON.parse(userStorage.getItem(props.storageKey) || 'null') } catch {}
    const matching = saved && (devices.value.find(device => device.index === saved.index && device.name === saved.name)
      || devices.value.find(device => device.name === saved.name))
    const preferred = (props.preferUsb || props.preferMicrophone)
      ? preferredRecordingDevice(devices.value, null, props.preferUsb ? 'usb' : 'microphone') : null
    const selected = matching || preferred || null
    selectedIndex.value = selected ? String(selected.index) : ''
    emit('change', selected)
    if (!devices.value.length) error.value = '未发现麦克风'
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
.microphone-label { flex: 1; min-width: 0; }
.microphone-label > span { flex: 0 0 84px; }
.microphone-label select { flex: 1; max-width: 100%; min-width: 100px; padding: 4px 6px; border: 1px solid #cbd5e1; border-radius: 6px; background: white; color: #334155; font: inherit; }
.microphone-control button { border: 0; background: transparent; color: #4f46e5; font: inherit; cursor: pointer; }
.microphone-control :disabled { opacity: .5; cursor: not-allowed; }
.microphone-error { color: #b45309; }
</style>
