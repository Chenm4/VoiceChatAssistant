import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import { createRenderer, h } from 'vue'
const { descriptor } = parse(readFileSync(new URL('../src/components/CodeHighlightPane.vue', import.meta.url), 'utf8'))
const compiled = compileScript(descriptor, { id: 'code-pane' }).content
  .replaceAll("from 'vue'", `from '${new URL('../node_modules/vue/index.mjs', import.meta.url)}'`)
const { default: Component } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)
Component.render = () => null
const renderer = createRenderer({ createComment: () => ({}), insert() {}, remove() {}, parentNode() {}, nextSibling() {} })

test('wheel zooms without modifier; pointer drags and arrows scroll without editing interference', () => {
  const original = globalThis.window
  globalThis.window = new EventTarget()
  const root = {}
  const vnode = h(Component, { code: { language: 'java', code: 'class Main {}' } })
  try {
    renderer.render(vnode, root)
    const state = vnode.component.setupState
    assert.equal(state.scale, 1.5)
    state.zoom({ deltaY: -100, deltaMode: 0 })
    assert.ok(state.scale > 1.5)
    for (let i = 0; i < 50; i++) state.zoom({ deltaY: -100, deltaMode: 0 })
    assert.equal(state.scale, 4)
    let movement = 0
    state.viewport = { scrollLeft: 0, scrollTop: 100, focus() {}, setPointerCapture() {}, hasPointerCapture: () => true, releasePointerCapture() {}, scrollBy: ({ top }) => { movement += top } }
    state.startDrag({ button: 0, pointerId: 1, clientX: 100, clientY: 100, preventDefault() {} })
    state.moveDrag({ pointerId: 1, clientX: 80, clientY: 40 })
    assert.equal(state.viewport.scrollTop, 160)
    assert.equal(state.viewport.scrollLeft, 20)
    state.endDrag({ pointerId: 1 })
    assert.equal(state.drag, null)
    state.keydown({ key: 'ArrowDown', preventDefault() {}, target: { closest: () => null } })
    assert.equal(movement, 64)
    state.keydown({ key: 'ArrowUp', preventDefault() {}, target: { closest: () => ({}) } })
    assert.equal(movement, 64)
  } finally {
    renderer.render(null, root)
    globalThis.window = original
  }
})
