import test from 'node:test'
import assert from 'node:assert/strict'
import { renderDoubaoMarkdown, transcriptLatestTop } from '../src/utils/doubaoTranscript.js'

test('renders streaming markdown titles, emphasis, lists and fenced code', () => {
  const html = renderDoubaoMarkdown('# 标题\n\n## 要点\n\n**重点**\n\n- 第一项\n- 第二项\n\n```js\nconst n = 1;\n```')
  assert.match(html, /<h1>标题<\/h1>/)
  assert.match(html, /<h2>要点<\/h2>/)
  assert.match(html, /<strong>重点<\/strong>/)
  assert.match(html, /<ul>/)
  assert.match(html, /<pre><code class="language-js">/)
  assert.doesNotMatch(renderDoubaoMarkdown('<script>alert(1)</script>'), /<script>/)
})

test('following latest anchors the content bottom independently of blank scroll space', () => {
  const viewport = { scrollTop: 100, clientHeight: 300, scrollHeight: 1200,
    getBoundingClientRect: () => ({ top: 50 }) }
  const contentEnd = { getBoundingClientRect: () => ({ top: 750 }) }
  assert.equal(transcriptLatestTop(viewport, contentEnd), 516)
  viewport.scrollHeight += 500
  assert.equal(transcriptLatestTop(viewport, contentEnd), 516)
  assert.equal(transcriptLatestTop(null, null), 0)
})
