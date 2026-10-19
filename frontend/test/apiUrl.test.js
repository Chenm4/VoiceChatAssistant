import test from 'node:test'
import assert from 'node:assert/strict'
import { apiUrl } from '../src/utils/apiUrl.js'

test('API paths use the deployment base for login, streams, media and sockets', () => {
  for (const path of ['/api', '/api/auth/login', '/api/chat', '/api/attachments/s/a?workspace_user=chenbo', '/api/doubao-realtime/ws']) {
    assert.equal(apiUrl(path, '/'), path)
    assert.equal(apiUrl(path, '/voicechat/'), '/voicechat' + path)
    assert.equal(apiUrl(apiUrl(path, '/voicechat/'), '/voicechat/'), '/voicechat' + path)
  }
})

test('non-API and external URLs are preserved', () => {
  for (const path of ['/apiculture', '/assets/index.js', 'https://example.com/api/chat', 'blob:example']) {
    assert.equal(apiUrl(path, '/voicechat/'), path)
  }
})
