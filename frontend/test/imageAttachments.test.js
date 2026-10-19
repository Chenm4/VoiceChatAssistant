import test from 'node:test'
import assert from 'node:assert/strict'
import { clipboardImages } from '../src/utils/imageAttachments.js'

test('extract pasted images without treating text as an image or duplicating files', () => {
  const image = { type: 'image/png', name: 'pasted.png' }
  const text = { kind: 'string', type: 'text/plain', getAsFile: () => null }
  assert.deepEqual(clipboardImages({ items: [text] }), [])
  assert.deepEqual(clipboardImages({ items: [text, { kind: 'file', type: image.type, getAsFile: () => image }], files: [image] }), [image])
  assert.deepEqual(clipboardImages({ files: [image, { type: 'text/plain' }] }), [image])
  assert.deepEqual(clipboardImages(null), [])
})
