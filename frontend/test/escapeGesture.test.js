import test from 'node:test'
import assert from 'node:assert/strict'
import { createEscapeGesture } from '../src/utils/escapeGesture.js'
function setup() {
  const calls = [], timers = new Map()
  let id = 0
  const gesture = createEscapeGesture({
    single: () => calls.push('stop'), double: () => calls.push('clear'),
    schedule: callback => { timers.set(++id, callback); return id },
    cancel: id => timers.delete(id)
  })
  const press = (extra = {}) => gesture.handle({ key: 'Escape', ...extra })
  const flush = () => { const callbacks = [...timers.values()]; timers.clear(); callbacks.forEach(fn => fn()) }
  return { calls, gesture, press, flush }
}
test('double Escape clears without stopping, and can be repeated', () => {
  const s = setup()
  s.press(); assert.deepEqual(s.calls, [])
  s.press(); s.flush(); assert.deepEqual(s.calls, ['clear'])
  s.press(); s.press(); s.flush(); assert.deepEqual(s.calls, ['clear', 'clear'])
})
test('single Escape stops only after the double-press window', () => {
  const s = setup()
  s.press(); assert.deepEqual(s.calls, [])
  s.flush(); assert.deepEqual(s.calls, ['stop'])
})
test('holding Escape does not count as double press; reset cancels pending stop', () => {
  const s = setup()
  s.press(); s.press({ repeat: true }); s.flush()
  assert.deepEqual(s.calls, ['stop'])
  s.press(); s.gesture.reset(); s.flush()
  assert.deepEqual(s.calls, ['stop'])
})
test('composition and modified keys are ignored', () => {
  const s = setup()
  assert.equal(s.press({ isComposing: true }), false)
  assert.equal(s.press({ ctrlKey: true }), false)
  s.flush(); assert.deepEqual(s.calls, [])
})
