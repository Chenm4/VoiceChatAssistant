import test from 'node:test'
import assert from 'node:assert/strict'
import { installMicrophoneContextMenu } from '../src/utils/microphoneContextMenu.js'

test('context menu toggles once and prevents native and component menus', () => {
  const target = new EventTarget()
  let toggles = 0, otherMenu = 0
  const cleanup = installMicrophoneContextMenu(target, () => toggles++)
  target.addEventListener('contextmenu', () => otherMenu++)
  const event = new Event('contextmenu', { cancelable: true })
  target.dispatchEvent(event)
  assert.equal(event.defaultPrevented, true)
  assert.equal(toggles, 1)
  assert.equal(otherMenu, 0)
  cleanup()
  const restored = new Event('contextmenu', { cancelable: true })
  target.dispatchEvent(restored)
  assert.equal(toggles, 1)
  assert.equal(otherMenu, 1)
  assert.equal(restored.defaultPrevented, false)
})

test('right mouse down cannot trigger draggable controls; left mouse down remains usable', () => {
  const target = new EventTarget()
  let controlDown = 0, toggles = 0
  const cleanup = installMicrophoneContextMenu(target, () => toggles++)
  target.addEventListener('mousedown', () => controlDown++)
  for (const [button, ctrlKey] of [[2, false], [0, true], [0, false]]) {
    const event = new Event('mousedown')
    Object.assign(event, { button, ctrlKey })
    target.dispatchEvent(event)
  }
  assert.equal(controlDown, 1)
  assert.equal(toggles, 0) // Only contextmenu, never mousedown, changes recording.
  cleanup()
})

test('right-click follows the current session action without installing duplicate listeners', () => {
  const target = new EventTarget()
  let action, recordings = 0, photos = 0
  const cleanup = installMicrophoneContextMenu(target, () => recordings++, {
    getAction: () => action,
    capturePhoto: () => photos++
  })
  target.dispatchEvent(new Event('contextmenu'))
  assert.equal(recordings, 1)
  action = 'photo'
  target.dispatchEvent(new Event('contextmenu'))
  assert.equal(photos, 1)
  assert.equal(recordings, 1)
  action = 'record'
  target.dispatchEvent(new Event('contextmenu'))
  assert.equal(recordings, 2)
  cleanup()
  target.dispatchEvent(new Event('contextmenu'))
  assert.equal(recordings, 2)
})

test('Enter outside the composer uses the same action as right-click', () => {
  const target = new EventTarget()
  let action = 'record', recordings = 0, photos = 0
  const cleanup = installMicrophoneContextMenu(target, () => recordings++, {
    getAction: () => action, capturePhoto: () => photos++
  })
  const press = properties => {
    const event = new Event('keydown', { cancelable: true })
    Object.assign(event, { key: 'Enter', ...properties })
    target.dispatchEvent(event)
    return event
  }
  assert.equal(press({}).defaultPrevented, true)
  assert.equal(recordings, 1)
  action = 'photo'
  press({})
  assert.equal(photos, 1)
  press({ repeat: true })
  press({ isComposing: true })
  press({ shiftKey: true })
  target.closest = () => ({ tagName: 'TEXTAREA' })
  assert.equal(press({}).defaultPrevented, false)
  assert.equal(photos, 1)
  cleanup()
  target.closest = undefined
  assert.equal(press({}).defaultPrevented, false)
  assert.equal(photos, 1)
})
