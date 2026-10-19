import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse as parseSfc } from '@vue/compiler-sfc'
import { parse } from '@babel/parser'
import { interruptAnswerStreams } from '../src/utils/interruptAnswerStreams.js'

const { descriptor } = parseSfc(readFileSync(new URL('../src/views/ChatView.vue', import.meta.url), 'utf8'))
const source = descriptor.scriptSetup.content
const ast = parse(source, { sourceType: 'module' })
function actualFunction(name, context) {
  const node = ast.program.body.find(node => node.type === 'FunctionDeclaration' && node.id.name === name)
  return new Function('context', `with (context) { return (${source.slice(node.start, node.end)}) }`)(context)
}

function stream() {
  const controller = new AbortController()
  controller.finished = new Promise(resolve => { controller.finish = resolve })
  return controller
}

test('send-button stop immediately resets camera busy state, aborts uploads and cancels all answer streams', async () => {
  const primary = stream()
  const photo = stream()
  const upload = new AbortController()
  let closed = false
  const released = []
  const context = {
    stoppingResponses: { value: false }, restartVersion: 0,
    restartingResponse: { value: true }, captureVersion: 4,
    isCapturing: { value: true }, captureConnected: { value: true },
    captureSourceName: { value: 'UGREEN 2K' },
    displayCapture: { stop() { closed = true } },
    captureUploadController: upload,
    captureQueue: { value: [{ sessionId: 'session', attachment: { id: 'queued' } }] },
    abortController: { value: primary }, captureControllers: new Set([photo]),
    interruptAnswerStreams, doubaoOverlay: { value: null },
    releaseUnusedCapture: (session, id) => released.push([session, id]),
    showNotification() {}
  }
  context.stopCaptureSource = actualFunction('stopCaptureSource', context)
  const stop = actualFunction('stopAllResponses', context)
  const stopping = stop()
  assert.equal(context.isCapturing.value, false)
  assert.equal(context.captureConnected.value, false)
  assert.equal(context.captureSourceName.value, '')
  assert.equal(context.captureVersion, 5)
  assert.equal(closed, true)
  assert.equal(upload.signal.aborted, true)
  assert.equal(context.captureQueue.value.length, 0)
  assert.deepEqual(released, [['session', 'queued']])
  assert.equal(primary.signal.reason, 'user-stop')
  assert.equal(photo.signal.reason, 'user-stop')
  assert.equal(context.stoppingResponses.value, true)
  primary.finish()
  photo.finish()
  await stopping
  assert.equal(context.stoppingResponses.value, false)
})
