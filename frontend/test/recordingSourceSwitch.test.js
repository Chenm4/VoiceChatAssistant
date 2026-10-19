import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse as parseSfc } from '@vue/compiler-sfc'
import { recordingRoute, recordingModeName } from '../src/utils/recordingRoute.js'
import { parse } from '@babel/parser'
const { descriptor } = parseSfc(readFileSync(new URL('../src/views/ChatView.vue', import.meta.url), 'utf8'))
const source = descriptor.scriptSetup.content
const ast = parse(source, { sourceType: 'module' })
function actual(name, context) {
  const node = ast.program.body.find(node => node.type === 'FunctionDeclaration' && node.id.name === name)
  return new Function('context', `with(context) { return (${source.slice(node.start,node.end)}) }`)(context)
}
function setup() {
  const context = {
    isProcessingRecording: { value: false }, recordingPhase: { value: 'idle' }, isRecording: { value: true },
    recordingInputSource: { value: 'usb' }, selectedUsbInput: { value: { index: 0, name: 'USB Audio' } },
    selectedMicrophone: { value: { index: 2, name: 'Mic' } }, inputMessage: { value: 'USB识别内容' },
    calls: [], notifications: [], recordingRevision: 0,
    buttonRecordingMode: { value: 'mix' }, rightClickRecordingMode: { value: 'usb' },
    activeRecordingMode: { value: 'usb' }, recordingModeLabel: { value: '声卡单录' },
    recordingRoute, recordingModeName,
    api: { async post(path, body) { context.calls.push([path, body]); return { success: true } } },
    handleStopRecording: () => assert.fail('Source switch must not stop recognition'),
    handleStartRecording: () => assert.fail('Source switch must not restart recognition'),
    showNotification: text => context.notifications.push(text),
  }
  context.latestRecordingTranscript = ''
  context.clearedTranscriptLength = 0
  context.recordingDraftPrefix = ''
  context.recordingComposerText = actual('recordingComposerText', context)
  context.routeForRecording = actual('routeForRecording', context)
  return context
}
test('USB to mic and back uses only switch API, preserves transcript and supports index zero', async () => {
  const context = setup()
  const toggle = actual('handleToggleRecording', context)
  await toggle('microphone')
  assert.equal(context.recordingInputSource.value, 'microphone')
  assert.equal(context.inputMessage.value, 'USB识别内容')
  await toggle('usb')
  assert.deepEqual(context.calls.map(call => call[0]), ['/recording/switch-input', '/recording/switch-input'])
  assert.equal(context.calls[0][1].mix_inputs, true)
  assert.equal(context.calls[1][1].mix_inputs, false)
  assert.equal(context.calls[1][1].input_device_index, 0)
  assert.equal(context.recordingInputSource.value, 'usb')
  assert.equal(context.recordingPhase.value, 'idle')
})
test('clicking current source stops and submits; hotkey also stops current USB source', async () => {
  const context = setup()
  let submitted = false
  context.handleStopRecording = async options => { submitted = options.sendMessage }
  await actual('handleToggleRecording', context)()
  assert.equal(submitted, true)
  assert.deepEqual(context.calls, [])
})
test('failed switch retains the previous source and text and releases the busy state', async () => {
  const context = setup()
  context.api.post = async () => { throw new Error('device unavailable') }
  await actual('handleToggleRecording', context)('microphone')
  assert.equal(context.recordingInputSource.value, 'usb')
  assert.equal(context.inputMessage.value, 'USB识别内容')
  assert.equal(context.isProcessingRecording.value, false)
  assert.match(context.notifications[0], /device unavailable/)
})
test('live status preserves the existing draft and cumulatively appends both selected sources', async () => {
  const context = setup()
  Object.assign(context, { recordingStatusPending: false, recordingAudioLevel: { value: 0 },
    captureWarningShown: false, recordingDraftPrefix: '已有草稿' })
  let partial = 'USB识别内容'
  context.api.get = async () => ({ is_recording: true, partial_text: partial })
  const check = actual('checkRecordingStatus', context)
  await check()
  assert.equal(context.inputMessage.value, '已有草稿\nUSB识别内容')
  partial += '，接着是麦克风内容'
  await check()
  assert.equal(context.inputMessage.value, '已有草稿\nUSB识别内容，接着是麦克风内容')
})

test('microphone to right-click activates USB recognition without stopping the stream', async () => {
  const context = setup()
  context.recordingInputSource.value = 'microphone'
  await actual('handleToggleRecording', context)('usb')
  assert.equal(context.isRecording.value, true)
  assert.equal(context.recordingInputSource.value, 'usb')
  assert.equal(context.calls[0][0], '/recording/switch-input')
})
test('ended old capture is preserved and the requested right-click capture starts in order', async () => {
  const context = setup()
  context.recordingInputSource.value = 'microphone'
  context.api.post = async () => { throw { response: { status: 409 } } }
  const order = []
  context.handleStopRecording = async options => {
    assert.deepEqual(options, { sendMessage: false, silent: true })
    order.push('stop')
    context.isRecording.value = false
  }
  context.handleStartRecording = async source => {
    order.push(source)
    context.isRecording.value = true
    context.recordingInputSource.value = source
  }
  await actual('handleToggleRecording', context)('usb')
  assert.deepEqual(order, ['stop', 'usb'])
  assert.equal(context.isRecording.value, true)
  assert.equal(context.inputMessage.value, 'USB识别内容')
})
test('status response from before a source switch cannot stop the new recognition', async () => {
  const context = setup()
  Object.assign(context, { recordingStatusPending: false, recordingAudioLevel: { value: 0 } })
  let resolve
  context.api.get = () => new Promise(done => { resolve = done })
  const pending = actual('checkRecordingStatus', context)()
  await actual('handleToggleRecording', context)('microphone')
  resolve({ is_recording: false, error: 'old capture ended' })
  await pending
  assert.equal(context.isRecording.value, true)
  assert.equal(context.recordingInputSource.value, 'microphone')
})
test('status polling does not run while a source switch is pending', async () => {
  const context = setup()
  context.recordingStatusPending = false
  context.recordingPhase.value = 'switching'
  context.api.get = () => assert.fail('must not poll during source switch')
  await actual('checkRecordingStatus', context)()
})


test('clearing during recognition keeps capture running and only new transcript returns', async () => {
  const context = setup()
  Object.assign(context, { recordingStatusPending: false, recordingAudioLevel: { value: 0 },
    captureWarningShown: false, recordingDraftPrefix: '草稿' })
  let partial = '之前说的话'
  context.api.get = async () => ({ is_recording: true, partial_text: partial })
  const check = actual('checkRecordingStatus', context)
  await check()
  actual('clearComposerOnly', context)()
  assert.equal(context.inputMessage.value, '')
  assert.equal(context.isRecording.value, true)
  assert.deepEqual(context.calls, [])
  await check()
  assert.equal(context.inputMessage.value, '')
  partial += '新的内容'
  await check()
  assert.equal(context.inputMessage.value, '新的内容')
  assert.equal(context.recordingComposerText(partial + '。'), '新的内容。')
  actual('clearComposerOnly', context)()
  assert.equal(context.recordingComposerText(partial + '。再说'), '再说')
})
