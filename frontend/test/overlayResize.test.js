import test from 'node:test'
import assert from 'node:assert/strict'
import { resizeOverlay } from '../src/utils/overlayResize.js'

const rect = { x: 200, y: 180, width: 460, height: 320 }
const viewport = { width: 1200, height: 800 }
for (const corner of ['nw', 'ne', 'sw', 'se']) {
  test(`${corner}: width and height change while opposite corner stays fixed`, () => {
    const next = resizeOverlay(rect, corner, corner.includes('w') ? -80 : 80, corner.includes('n') ? -60 : 60, viewport)
    assert.equal(next.width, 540)
    assert.equal(next.height, 380)
    assert.equal(corner.includes('w') ? next.x + next.width : next.x, corner.includes('w') ? rect.x + rect.width : rect.x)
    assert.equal(corner.includes('n') ? next.y + next.height : next.y, corner.includes('n') ? rect.y + rect.height : rect.y)
  })
}
test('northwest minimum dimensions do not drift the opposite corner', () => {
  const next = resizeOverlay(rect, 'nw', 2000, 2000, viewport)
  assert.deepEqual(next, { x: 380, y: 360, width: 280, height: 140 })
})
test('all corners stay within viewport at maximum size', () => {
  for (const corner of ['nw', 'ne', 'sw', 'se']) {
    const next = resizeOverlay(rect, corner, corner.includes('w') ? -2000 : 2000, corner.includes('n') ? -2000 : 2000, viewport)
    assert.ok(next.x >= 0 && next.y >= 0)
    assert.ok(next.x + next.width <= viewport.width && next.y + next.height <= viewport.height)
  }
})
test('collapsed toolbar can change width without moving vertically', () => {
  const next = resizeOverlay({ ...rect, height: 40 }, 'nw', -80, -90, viewport, true)
  assert.deepEqual(next, { x: 120, y: 180, width: 540, height: 40 })
})
test('empty compact toolbar does not jump taller on horizontal resizing', () => {
  const next = resizeOverlay({ ...rect, height: 40 }, 'se', 80, 0, viewport)
  assert.equal(next.height, 40)
})

test('panel growing near bottom or right edge is moved completely back on screen', async () => {
  const { fitOverlayRect } = await import('../src/utils/overlayResize.js')
  assert.deepEqual(fitOverlayRect({ x: 1000, y: 760, width: 460, height: 350 }, viewport),
    { x: 740, y: 450, width: 460, height: 350 })
  assert.deepEqual(fitOverlayRect({ x: -40, y: -70, width: 460, height: 350 }, viewport),
    { x: 0, y: 0, width: 460, height: 350 })
})

test('viewport smaller than panel clamps both size and position', async () => {
  const { fitOverlayRect } = await import('../src/utils/overlayResize.js')
  assert.deepEqual(fitOverlayRect({ x: 600, y: 700, width: 460, height: 350 }, { width: 320, height: 200 }),
    { x: 0, y: 0, width: 320, height: 200 })
})

test('free floating resize keeps a partly offscreen panel offscreen and its dimensions positive', async () => {
  const { resizeFloatingOverlay } = await import('../src/utils/overlayResize.js')
  const outside = { x: 1100, y: -80, width: 460, height: 320 }
  const next = resizeFloatingOverlay(outside, 'se', 100, 80, viewport)
  assert.deepEqual(next, { x: 1100, y: -80, width: 560, height: 400 })
  const west = resizeFloatingOverlay(outside, 'nw', 100, 80, viewport)
  assert.equal(west.x + west.width, outside.x + outside.width)
  assert.equal(west.y + west.height, outside.y + outside.height)
})
