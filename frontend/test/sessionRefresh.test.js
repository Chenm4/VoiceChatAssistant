import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse as parseSfc } from '@vue/compiler-sfc'
import { parse } from '@babel/parser'

const { descriptor } = parseSfc(readFileSync(new URL('../src/views/ChatView.vue', import.meta.url), 'utf8'))
const source = descriptor.scriptSetup.content
const ast = parse(source, { sourceType: 'module' })
function actualFunction(name, context) {
  const node = ast.program.body.find(node => node.type === 'FunctionDeclaration' && node.id.name === name)
  return new Function('context', `with(context) { return (${source.slice(node.start,node.end)}) }`)(context)
}
function setup() {
  const messages = [{ role: 'user', content: 'saved question' }, { role: 'assistant', content: 'partial answer' }]
  const context = {
    currentSessionId: { value: 'history' },
    displayedSessionId: 'history',
    sessions: { value: [{ id: 'history', session_config: { right_click_action: 'photo' } }] },
    messages: { value: messages }, messageListRef: { value: null }, nextTick: async () => {}, showNotification() {}, requests: [],
    api: { async get(path) {
      context.requests.push(path)
      if (path === '/sessions') return { current_session_id: 'empty', sessions: [{ id: 'empty' }, { id: 'history' }] }
      return { messages: [] }
    } }
  }
  context.loadSessionMessages = actualFunction('loadSessionMessages', context)
  context.loadSessions = actualFunction('loadSessions', context)
  return context
}

test('recording cancellation/sidebar refresh preserves selected history, partial answer and settings', async () => {
  const context = setup()
  const visible = context.messages.value
  await context.loadSessions()
  assert.equal(context.currentSessionId.value, 'history')
  assert.equal(context.messages.value, visible)
  assert.equal(context.messages.value[1].content, 'partial answer')
  assert.equal(context.sessions.value.find(session => session.id === 'history').session_config.right_click_action, 'photo')
  assert.deepEqual(context.requests, ['/sessions'])
})

test('explicit new-session selection still loads the new conversation', async () => {
  const context = setup()
  await context.loadSessions({ selectCurrent: true })
  assert.equal(context.currentSessionId.value, 'empty')
  assert.deepEqual(context.messages.value, [])
  assert.deepEqual(context.requests, ['/sessions', '/sessions/empty'])
})

test('late response from the old session cannot overwrite newly selected conversation', async () => {
  const context = setup()
  let resolve
  context.api.get = () => new Promise(done => { resolve = done })
  const loading = context.loadSessionMessages('history')
  context.currentSessionId.value = 'other'
  const visible = context.messages.value
  resolve({ messages: [] })
  await loading
  assert.equal(context.messages.value, visible)
})

test('cancel recording keeps draft and current selection instead of switching to recording session', async () => {
  const context = setup()
  Object.assign(context, {
    recordingRevision: 0, recordingPhase: { value: 'idle' }, isRecording: { value: true },
    recordingStatusInterval: null, recordingSessionId: 'original-recording-session',
    recordingWithDoubao: false, recordingDraftPrefix: '', inputMessage: { value: '' },
    escapeGesture: { reset() {} }, recordingComposerText: text => text,
    handleSwitchSession: () => assert.fail('Cancellation must not switch sessions'),
  })
  context.api.post = async path => {
    assert.equal(path, '/recording/stop?finalize=false')
    assert.equal(context.recordingPhase.value, 'cancelling')
    return { success: true, text: 'recognized draft' }
  }
  const stop = actualFunction('handleStopRecording', context)
  const visible = context.messages.value
  await stop({ sendMessage: false })
  assert.equal(context.inputMessage.value, 'recognized draft')
  assert.equal(context.currentSessionId.value, 'history')
  assert.equal(context.messages.value, visible)
})


test('answer completion refresh restores the visible reading position', async () => {
  const context = setup()
  const calls = []
  const position = { top: 520, index: '1', offset: -32 }
  context.messageListRef.value = {
    captureReadingPosition: () => { calls.push('capture'); return position },
    restoreReadingPosition: value => { calls.push('restore'); assert.equal(value, position) },
    scrollToBottom: () => assert.fail('Completion must not jump to the newest answer')
  }
  context.api.get = async () => ({ messages: [
    { role: 'user', content: 'saved question' },
    { role: 'assistant', content: 'final answer' }
  ] })
  await context.loadSessionMessages('history')
  assert.deepEqual(calls, ['capture', 'restore'])
  assert.equal(context.messages.value[1].content, 'final answer')
})
