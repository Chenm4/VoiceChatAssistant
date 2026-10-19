import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import { createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'

const { descriptor } = parse(readFileSync(new URL('../src/components/InputArea.vue', import.meta.url), 'utf8'))
const compiled = compileScript(descriptor, { id: 'input-stop-test', inlineTemplate: true }).content
  .replaceAll('from "vue"', `from '${new URL('../node_modules/vue/index.mjs', import.meta.url)}'`)
  .replaceAll("from 'vue'", `from '${new URL('../node_modules/vue/index.mjs', import.meta.url)}'`)
  .replace("from '../utils/imageAttachments'", `from '${new URL('../src/utils/imageAttachments.js', import.meta.url)}'`)
const { default: Component } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)

async function sendButton(props) {
  const app = createSSRApp(Component, { modelValue: '', ...props })
  app.component('el-popover', { setup: (_, { slots }) => () => h('div', slots.default?.()) })
  app.component('el-button', { setup: (_, { slots }) => () => h('button', slots.default?.()) })
  const html = await renderToString(app)
  return html.match(/<button\b[^>]*class="send-button[^>]*>[\s\S]*?<\/button>/)[0]
}

test('parallel photo and ordinary generation both expose an enabled stop button even with empty input', async () => {
  for (const props of [{ captureResponsesActive: true }, { isSending: true }]) {
    const button = await sendButton({ ...props, isUploadingImages: true })
    assert.match(button, /aria-label="停止生成"/)
    assert.match(button, /stop-icon/)
    assert.match(button, /class="stop-label">停止生成<\/span>/)
    assert.doesNotMatch(button, /\bdisabled(?:[\s=>])/)
  }
})

test('empty idle composer and stop in progress remain disabled', async () => {
  assert.match(await sendButton({}), /\bdisabled/)
  const stopping = await sendButton({ isSending: true, isStopping: true })
  assert.match(stopping, /\bdisabled/)
  assert.match(stopping, /aria-label="正在停止…"/)
})
