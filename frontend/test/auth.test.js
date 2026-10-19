import test from 'node:test'
import assert from 'node:assert/strict'
import { setUsername, userStorage, authFetch, privateUrl, migrateLegacyPreferences } from '../src/utils/auth.js'

test('preferences are independent, and only chenbo inherits legacy settings', () => {
  const old = globalThis.localStorage
  const values = new Map([['captureCameraId', 'legacy-camera'], ['chatLayoutPreferences', '{"header":"bottom"}']])
  globalThis.localStorage = {
    get length() { return values.size }, key: i => [...values.keys()][i],
    getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key)
  }
  try {
    setUsername('chenshuai'); migrateLegacyPreferences()
    assert.equal(userStorage.getItem('captureCameraId'), null)
    userStorage.setItem('captureCameraId', 'shuai-camera')
    setUsername('chenbo'); migrateLegacyPreferences()
    assert.equal(userStorage.getItem('captureCameraId'), 'legacy-camera')
    userStorage.setItem('captureCameraId', 'bo-camera')
    migrateLegacyPreferences()
    assert.equal(userStorage.getItem('captureCameraId'), 'bo-camera')
    setUsername('chenshuai')
    assert.equal(userStorage.getItem('captureCameraId'), 'shuai-camera')
    setUsername('')
    assert.throws(() => userStorage.getItem('captureCameraId'))
  } finally { globalThis.localStorage = old; setUsername('') }
})

test('requests and media carry the mounted identity; 401 expires the page', async () => {
  const old = { window: globalThis.window, fetch: globalThis.fetch }
  const events = []
  globalThis.window = { location: { origin: 'https://example.test' }, dispatchEvent: event => events.push(event.type) }
  let captured
  globalThis.fetch = async (url, options) => { captured = { url, options }; return { status: 401 } }
  try {
    setUsername('chenbo')
    await authFetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' } })
    assert.equal(captured.options.headers.get('X-Workspace-User'), 'chenbo')
    assert.equal(captured.options.headers.get('Content-Type'), 'application/json')
    assert.equal(captured.options.credentials, 'same-origin')
    assert.deepEqual(events, ['auth-expired'])
    assert.equal(privateUrl('/api/attachments/s/a'), '/api/attachments/s/a?workspace_user=chenbo')
  } finally { Object.assign(globalThis, old); setUsername('') }
})
