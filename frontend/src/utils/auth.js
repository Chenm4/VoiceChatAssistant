import { apiUrl } from './apiUrl.js'

// Identity is held by the mounted page. A stale tab never silently becomes another user.
let username = ''
export const currentUsername = () => username
export function setUsername(value) { username = value || '' }
export function authHeaders() { return username ? { 'X-Workspace-User': username } : {} }
export function privateUrl(value) {
  const url = new URL(value, window.location.origin)
  if (username) url.searchParams.set('workspace_user', username)
  return apiUrl(url.pathname + url.search)
}
export function sessionExpired() { window.dispatchEvent(new Event('auth-expired')) }
export async function authFetch(url, options = {}) {
  const headers = new Headers(options.headers)
  for (const [key, value] of Object.entries(authHeaders())) headers.set(key, value)
  const response = await fetch(apiUrl(url), { ...options, headers, credentials: 'same-origin' })
  if (response.status === 401) sessionExpired()
  return response
}
// Preferences are never read from the old shared keys or another user's namespace.
export const userStorage = {
  key(key) {
    if (!username) throw new Error('请先登录')
    return `voice:${username}:${key}`
  },
  getItem(key) { return localStorage.getItem(this.key(key)) },
  setItem(key, value) { localStorage.setItem(this.key(key), value) },
  removeItem(key) { localStorage.removeItem(this.key(key)) }
}
export function announceAuthChange() {
  localStorage.setItem('voice:auth-change', `${Date.now()}:${Math.random()}`)
}

export function migrateLegacyPreferences() {
  if (username !== 'chenbo' || userStorage.getItem('migration-v1')) return
  const known = new Set(['scene-rerun', 'captureButtonSize', 'captureButtonPosition', 'recordingButtonMode',
    'recordingRightClickMode', 'recordingMicrophone', 'recordingUsbInput', 'chatLayoutPreferences',
    'captureCameraId', 'hasConfig', 'hasSeenHotkeyTip', 'sessionSettingsWidth', 'multiModelDisplayPreferences'])
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if ((known.has(key) || key.startsWith('prompt-scene-position:')) && userStorage.getItem(key) === null) {
      userStorage.setItem(key, localStorage.getItem(key))
    }
  }
  userStorage.setItem('migration-v1', 'true')
}
