import test from 'node:test'
import assert from 'node:assert/strict'
import { interruptAnswerStreams } from '../src/utils/interruptAnswerStreams.js'

function stream() {
  const controller = new AbortController()
  controller.finished = new Promise(resolve => { controller.finish = resolve })
  return controller
}

test('interrupts ordinary and parallel streams immediately, waits for every cleanup', async () => {
  const primary = stream()
  const first = stream()
  const second = stream()
  let complete = false
  const pending = interruptAnswerStreams(primary, new Set([first, second]))
    .then(() => { complete = true })
  for (const controller of [primary, first, second]) {
    assert.equal(controller.signal.aborted, true)
    assert.equal(controller.signal.reason, 'message-edit')
  }
  primary.finish()
  first.finish()
  await Promise.resolve()
  assert.equal(complete, false)
  second.finish()
  await pending
  assert.equal(complete, true)
})

test('no active streams and repeated interruptions are safe', async () => {
  await interruptAnswerStreams(null)
  const controller = stream()
  controller.finish()
  await interruptAnswerStreams(controller, [controller])
  await interruptAnswerStreams(controller)
  assert.equal(controller.signal.aborted, true)
})

test('explicit stop aborts all parallel requests and keeps user-stop distinct from editing', async () => {
  const primary = stream()
  const first = stream()
  const second = stream()
  const stopping = interruptAnswerStreams(primary, new Set([first, second]), 'user-stop')
  for (const controller of [primary, first, second]) {
    assert.equal(controller.signal.aborted, true)
    assert.equal(controller.signal.reason, 'user-stop')
    controller.finish()
  }
  await stopping
})
