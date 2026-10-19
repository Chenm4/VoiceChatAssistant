<template>
  <section class="voice-settings" aria-label="语音服务配置">
    <h3>语音识别与豆包配置</h3>
    <p>仅保存到当前账号。豆包默认关闭，可在聊天页手动开启。</p>
    <p>麦克风由当前浏览器采集，请允许网站的麦克风权限。</p>
    <p v-if="loading">正在加载语音配置…</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <form v-if="settings" @submit.prevent="save">
      <label>语音识别服务
        <select v-model="settings.provider">
          <option value="soniox">Soniox</option>
          <option value="volcengine">火山引擎 ASR</option>
        </select>
      </label>
      <label>Soniox API Key<SecretField v-model="settings.soniox_api_key" label="Soniox API Key" /></label>
      <label>火山 ASR App ID<input v-model="settings.volcengine_app_id" autocomplete="off"></label>
      <label>火山 ASR Token<SecretField v-model="settings.volcengine_token" label="火山 ASR Token" /></label>
      <label>豆包 App ID<input v-model="settings.doubao_app_id" autocomplete="off"></label>
      <label>豆包 Access Token<SecretField v-model="settings.doubao_access_token" label="豆包 Access Token" /></label>
      <button type="submit" :disabled="saving">{{ saving ? '保存中…' : '保存语音配置' }}</button>
      <span v-if="saved" role="status">已保存，新录音立即生效</span>
    </form>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../utils/api'
import SecretField from './SecretField.vue'

const settings = ref(null), loading = ref(true), saving = ref(false), saved = ref(false), error = ref('')
onMounted(async () => {
  try { settings.value = await api.get('/voice-settings') }
  catch (failure) { error.value = failure.response?.data?.detail || '无法加载语音配置，请重新打开设置' }
  finally { loading.value = false }
})
async function save() {
  saving.value = true
  error.value = ''
  saved.value = false
  try { await api.post('/voice-settings', settings.value); saved.value = true }
  catch (failure) { error.value = failure.response?.data?.detail || '保存失败，请重试' }
  finally { saving.value = false }
}
</script>

<style scoped>
.voice-settings { margin-top: 20px; padding: 16px; border: 1px solid #e2e8f0; border-radius: 10px; }
h3 { font-weight: 600; }
p { margin: 8px 0; font-size: 13px; color: #64748b; }
form, label { display: flex; flex-direction: column; gap: 8px; }
form { gap: 14px; }
input, select { padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 8px; }
button { padding: 10px; color: white; background: #2563eb; border-radius: 8px; }
button:disabled { opacity: .5; }
[role="alert"] { color: #b91c1c; }
</style>
