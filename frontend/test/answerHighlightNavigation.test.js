import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import { createRenderer, h, nextTick, reactive } from 'vue'

const { descriptor } = parse(readFileSync(new URL('../src/components/AnswerHighlight.vue', import.meta.url), 'utf8'))
const compiled = compileScript(descriptor, { id: 'navigation-test' }).content
  .replace("import CodeHighlightPane from './CodeHighlightPane.vue'", 'const CodeHighlightPane = {}')
  .replaceAll("from 'vue'", `from '${new URL('../node_modules/vue/index.mjs', import.meta.url)}'`)
  .replace("from '../utils/answerHighlight'", `from '${new URL('../src/utils/answerHighlight.js', import.meta.url)}'`)
const { default: Component } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)
Component.render = () => null
const renderer = createRenderer({
  createComment: () => ({}), insert() {}, remove() {}, parentNode() {}, nextSibling() {}
})
const reply = (id, questions) => ({
  id, role: 'assistant', content: '```json\n' + JSON.stringify({ answer_highlight: {
    answers: questions.map(question => ({ question, type: 'choice', answer: 'A' }))
  } }) + '\n```'
})

test('buttons navigate history, clamp at ends, retain review selection and survive late answers', async () => {
  const originalWindow = globalThis.window
  globalThis.window = new EventTarget()
  const messages = reactive([reply('old', ['1', '2']), reply('new', ['3', '4'])])
  const navigated = []
  const vnode = h(Component, { messages, onNavigate: index => navigated.push(index) })
  const root = {}
  try {
    renderer.render(vnode, root)
    const state = vnode.component.setupState
    assert.equal(state.activePage.question, '3')
    state.onWheel({ deltaY: 100, deltaMode: 0 })
    assert.equal(state.activePage.question, '4')
    state.navigate(1)
    assert.equal(state.activePage.question, '4')
    state.navigate(-1)
    state.navigate(-1)
    assert.equal(state.activePage.question, '2')
    assert.equal(navigated.at(-1), 0)
    messages.push(reply('latest', ['5']))
    await nextTick()
    assert.equal(state.activePage.question, '2')
    state.navigate(-1)
    state.navigate(-1)
    assert.equal(state.activePage.question, '1')
    state.onClick({ button: 0, detail: 3, target: { closest: () => ({}) } })
    assert.equal(state.dismissed, false)
    const click = { button: 0, detail: 3, target: { closest: () => null } }
    state.onClick({ ...click, detail: 2 })
    assert.equal(state.dismissed, false)
    state.onPointerDown({ clientX: 0, clientY: 0 })
    state.onPointerMove({ clientX: 0, clientY: 40 })
    state.onClick(click)
    assert.equal(state.dismissed, false)
    state.onPointerDown({ clientX: 0, clientY: 0 })
    state.onClick(click)
    assert.equal(state.dismissed, true)
    state.dismissed = false
    state.onKeyDown({ key: 'Escape' })
    assert.equal(state.dismissed, true)
    messages[0].content = reply('old', ['1', '2', '6']).content
    await nextTick()
    assert.equal(state.dismissed, true)
    messages.splice(0)
    await nextTick()
    assert.equal(state.hasAnswers, false)
    messages.push(reply('fresh', ['7']))
    await nextTick()
    assert.equal(state.activePage.question, '7')
    assert.equal(state.dismissed, false)
  } finally {
    renderer.render(null, root)
    globalThis.window = originalWindow
  }
})

test('a new question marks the visible answer stale until its own answer arrives', async () => {
  const originalWindow = globalThis.window
  globalThis.window = new EventTarget()
  const messages = reactive([{ role: 'user', content: 'first' }, reply('first', ['1'])])
  const vnode = h(Component, { messages })
  const root = {}
  try {
    renderer.render(vnode, root)
    const state = vnode.component.setupState
    const firstKey = state.activePage.key
    assert.equal(state.isStale, false)
    messages.push({ role: 'user', content: 'second' })
    await nextTick()
    assert.equal(state.isStale, true)
    assert.equal(state.activePage.key, firstKey)
    assert.equal(state.hasAnswers, true)
    assert.equal(state.dismissed, false)
    messages.push({ role: 'assistant', content: '', is_streaming: true })
    await nextTick()
    assert.equal(state.activePage.key, firstKey)
    messages.at(-1).content = reply('second', ['2']).content
    await nextTick()
    assert.equal(state.isStale, true)
    messages.at(-1).is_streaming = false
    await nextTick()
    assert.equal(state.activePage.question, '2')
    assert.equal(state.isStale, false)
    state.navigate(-1)
    assert.equal(state.isStale, true)
    state.navigate(1)
    assert.equal(state.isStale, false)
    // An older request finishing late must not mark its answer as current.
    messages.push({ role: 'user', content: 'third' })
    messages[1].content = reply('first', ['1', 'extra']).content
    await nextTick()
    assert.equal(state.activePage.question, '2')
    assert.equal(state.isStale, true)
  } finally {
    renderer.render(null, root)
    globalThis.window = originalWindow
  }
})

test('server-assigned IDs preserve the selected question and dismissed state', async () => {
  const originalWindow = globalThis.window
  globalThis.window = new EventTarget()
  const messages = reactive([reply(undefined, ['1', '2'])])
  const vnode = h(Component, { messages })
  const root = {}
  try {
    renderer.render(vnode, root)
    const state = vnode.component.setupState
    state.navigate(1)
    state.dismissed = true
    messages.splice(0, 1, reply('saved', ['1', '2']))
    await nextTick()
    assert.equal(state.activePage.question, '2')
    assert.equal(state.dismissed, true)
  } finally {
    renderer.render(null, root)
    globalThis.window = originalWindow
  }
})
