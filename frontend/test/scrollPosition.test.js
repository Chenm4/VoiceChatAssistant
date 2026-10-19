import test from 'node:test'
import assert from 'node:assert/strict'
import { captureReadingPosition, restoreReadingPosition } from '../src/utils/scrollPosition.js'

test('refresh preserves the visible message offset after content above changes height', () => {
  let y = 90
  const anchor = { getBoundingClientRect: () => ({ top: y, bottom: y + 300 }), getAttribute: () => '2' }
  const scroller = { scrollTop: 600, getBoundingClientRect: () => ({ top: 100 }),
    querySelectorAll: () => [anchor], querySelector: () => anchor }
  const position = captureReadingPosition(scroller)
  y = 170
  restoreReadingPosition(scroller, position)
  assert.equal(scroller.scrollTop, 680)
})

test('blank reading space keeps its scroll position when no message is visible', () => {
  const scroller = { scrollTop: 800, getBoundingClientRect: () => ({ top: 0 }),
    querySelectorAll: () => [], querySelector: () => null }
  const position = captureReadingPosition(scroller)
  scroller.scrollTop = 500
  restoreReadingPosition(scroller, position)
  assert.equal(scroller.scrollTop, 800)
})

test('refresh does not jump to a different message that reuses the old index', () => {
  const oldAnchor = { getBoundingClientRect: () => ({ top: 90, bottom: 390 }),
    getAttribute: name => name === 'data-message-id' ? 'original' : '2' }
  let anchors = [oldAnchor]
  const scroller = { scrollTop: 600, getBoundingClientRect: () => ({ top: 100 }),
    querySelectorAll: () => anchors }
  const position = captureReadingPosition(scroller)
  anchors = [{ getBoundingClientRect: () => ({ top: 170, bottom: 470 }),
    getAttribute: name => name === 'data-message-id' ? 'replacement' : '2' }]
  restoreReadingPosition(scroller, position)
  assert.equal(scroller.scrollTop, 600)
})
