import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse as parseSfc } from '@vue/compiler-sfc'
import { parse } from '@babel/parser'

const { descriptor } = parseSfc(readFileSync(new URL('../src/views/ChatView.vue', import.meta.url), 'utf8'))
const source = descriptor.scriptSetup.content
const node = parse(source, { sourceType: 'module' }).program.body.find(node =>
  node.type === 'FunctionDeclaration' && node.id.name === 'handleResetCapture')

function setup(type) {
  const context = {
    isCapturing: { value: false }, stoppingResponses: { value: false }, captureVersion: 0,
    captureConnected: { value: false }, captureSourceName: { value: '' }, captureSourceType: { value: type },
    ensureDisplayCapture: () => ({ stop() {} }),
    async selectCaptureSource() { context.captureConnected.value = true },
    showNotification() {},
    async handleCaptureAndSend() { assert.equal(context.isCapturing.value, false); context.captures++ },
    captures: 0
  }
  context.reset = new Function('context', `with(context) { return (${source.slice(node.start,node.end)}) }`)(context)
  return context
}

test('selecting a window takes a screenshot immediately after connection', async () => {
  const context = setup('screen')
  await context.reset()
  assert.equal(context.captures, 1)
})

test('camera connection remains separate from explicitly taking a photo', async () => {
  const context = setup('camera')
  await context.reset()
  assert.equal(context.captures, 0)
  assert.equal(context.captureConnected.value, true)
})

test('cancelled selection or stop while picker is open does not capture', async () => {
  for (const stopped of [false, true]) {
    const context = setup('screen')
    context.selectCaptureSource = async () => {
      if (stopped) context.captureVersion++
      throw new DOMException('cancelled', 'AbortError')
    }
    await context.reset()
    assert.equal(context.captures, 0)
  }
})
