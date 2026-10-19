import test from 'node:test'
import assert from 'node:assert/strict'
import { DoubaoRealtime } from '../src/utils/doubaoRealtime.js'

test('only explicit completed-recording submission opens transport; binary output is ignored', () => {
  const previous = { window: globalThis.window, WebSocket: globalThis.WebSocket }
  const sockets = []
  globalThis.window = { location: { href: 'http://localhost:8888' } }
  globalThis.WebSocket = class {
    static OPEN = 1
    constructor() { this.readyState = 1; this.sent = []; sockets.push(this) }
    send(data) { this.sent.push(JSON.parse(data)) }
    close() { this.didClose = true }
  }
  try {
    const received = []; let closed = 0
    const client = new DoubaoRealtime(event => received.push(event), () => closed++)
    assert.equal(sockets.length, 0)
    client.start({ session_id: 's', audio_file: 'recording.wav', text: '完整问题' })
    const ws = sockets[0]; ws.onopen()
    assert.deepEqual(ws.sent, [{ type: 'start', session_id: 's', audio_file: 'recording.wav', text: '完整问题' }])
    ws.onmessage({ data: new ArrayBuffer(640) })
    assert.equal(received.length, 0)
    ws.onmessage({ data: JSON.stringify({ type: 'complete' }) })
    assert.equal(closed, 1)
    assert.equal(ws.didClose, true)
    client.close()
    assert.equal(closed, 1)
  } finally { Object.assign(globalThis, previous) }
})
