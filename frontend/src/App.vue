<template>
  <div id="app" class="min-h-screen bg-gray-50">
    <main v-if="checking" class="login-shell"><p>正在检查登录状态…</p></main>
    <main v-else-if="!user" class="login-shell">
      <form class="login-card" @submit.prevent="login">
        <div class="login-mark">V</div>
        <h1>登录语音助手</h1>
        <p>你的对话、提示词和设置，仅在你的账户中使用。</p>
        <label for="username">用户名</label>
        <input id="username" v-model.trim="form.username" autocomplete="username" required autofocus />
        <label for="password">密码</label>
        <input id="password" v-model="form.password" type="password" autocomplete="current-password" required />
        <p v-if="error" class="login-error" role="alert">{{ error }}</p>
        <button class="login-submit" :disabled="busy">{{ busy ? '正在登录…' : '登录' }}</button>
      </form>
    </main>
    <template v-else>
      <div class="account-bar"><span>当前用户：<strong>{{ user.username }}</strong></span><button :disabled="busy" @click="logout">退出登录</button></div>
      <ChatView v-if="currentView === 'chat'" :key="user.username" @open-prompt-lab="currentView = 'prompt-lab'" />
      <PromptLabView v-else :key="user.username" @back="currentView = 'chat'" />
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import ChatView from './views/ChatView.vue'
import PromptLabView from './views/PromptLabView.vue'
import { setUsername, authFetch, announceAuthChange, migrateLegacyPreferences } from './utils/auth'
import { apiUrl } from './utils/apiUrl.js'

const currentView = ref('chat')
const user = ref(null)
const checking = ref(true)
const busy = ref(false)
const error = ref('')
const form = reactive({ username: '', password: '' })
async function checkLogin() {
  try {
    const response = await fetch(apiUrl('/api/auth/me'), { cache: 'no-store' })
    if (response.ok) {
      const identity = await response.json()
      setUsername(identity.username)
      try { migrateLegacyPreferences() } catch { /* Storage may be disabled. */ }
      user.value = identity
    }
  } catch { error.value = '无法连接服务，请稍后重试' }
  finally { checking.value = false }
}
async function login() {
  busy.value = true
  error.value = ''
  try {
    const response = await fetch(apiUrl('/api/auth/login'), {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form)
    })
    const result = await response.json()
    if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : '登录失败')
    form.password = ''
    announceAuthChange()
    // Fresh document clears in-flight UI state and all component caches.
    window.location.reload()
  } catch (err) { error.value = err.message || '登录失败' }
  finally { busy.value = false }
}
async function logout() {
  busy.value = true
  try {
    const response = await authFetch('/api/auth/logout', { method: 'POST' })
    if (!response.ok && response.status !== 401) throw new Error('退出失败，请重试')
    announceAuthChange()
    window.location.reload()
  } catch (err) { window.alert(err.message) }
  finally { busy.value = false }
}
function expired() { window.location.reload() }
function storageChanged(event) { if (event.key === 'voice:auth-change') window.location.reload() }
onMounted(() => {
  window.addEventListener('auth-expired', expired)
  window.addEventListener('storage', storageChanged)
  checkLogin()
})
onUnmounted(() => {
  window.removeEventListener('auth-expired', expired)
  window.removeEventListener('storage', storageChanged)
})
</script>

<style scoped>
.login-shell { min-height: 100vh; display: grid; place-items: center; padding: 24px; background: #f4f6f9; }
.login-card { width: min(100%, 400px); padding: 36px; background: white; border: 1px solid #e4e8ef; border-radius: 20px; box-shadow: 0 16px 48px #152b5010; }
.login-mark { width: 40px; height: 40px; display: grid; place-items: center; background: #2563eb; color: white; font-size: 22px; font-weight: 700; border-radius: 12px; margin-bottom: 20px; }
h1 { font-size: 24px; font-weight: 650; color: #172335; }
.login-card > p { font-size: 13px; line-height: 1.7; color: #667085; margin: 10px 0 24px; }
label { display: block; margin: 16px 0 8px; font-size: 14px; color: #344054; }
input { width: 100%; border: 1px solid #cfd6e1; border-radius: 9px; padding: 11px 12px; }
input:focus { outline: 2px solid #93b4f8; outline-offset: 2px; }
.login-submit { width: 100%; background: #2563eb; color: white; padding: 12px; border-radius: 9px; margin-top: 24px; }
button:disabled { opacity: .6; cursor: wait; }
.login-card > .login-error { color: #c33737; margin-bottom: 0; }
.account-bar { position: fixed; z-index: 90; top: 5px; left: 50%; transform: translateX(-50%); display: flex; align-items: center; gap: 12px; padding: 4px 12px; border-radius: 20px; background: #fff; border: 1px solid #dbe3ef; font-size: 11px; color: #475569; }
.account-bar button { color: #2563eb; white-space: nowrap; }
</style>
