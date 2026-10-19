import test from 'node:test'
import assert from 'node:assert/strict'
import { algorithmAnswerParts } from '../src/utils/algorithmAnswer.js'

const wrap = code => '```json\n' + JSON.stringify({ algorithm_answer: { language: 'java', code } }) + '\n```'
test('extract code with real newlines, quotes and HTML as literal text, retaining explanation', () => {
  const code = 'class Main {\n  // <script>alert(1)</script>\n  String s = "hello";\n}'
  const parts = algorithmAnswerParts('思路\n' + wrap(code) + '\nO(n)')
  assert.deepEqual(parts, [{ type: 'markdown', text: '思路' }, { type: 'code', code, language: 'java' }, { type: 'markdown', text: '\nO(n)' }])
})
test('incomplete, invalid and unrelated JSON remain visible', () => {
  for (const content of [wrap('x').slice(0, -1), '```json\n{broken}\n```', '```json\n{"answer_highlight":{"answers":[]}}\n```', wrap('')]) {
    assert.deepEqual(algorithmAnswerParts(content), [{ type: 'markdown', text: content }])
  }
  assert.deepEqual(algorithmAnswerParts(), [])
})
test('multiple questions each render a card', () => {
  const parts = algorithmAnswerParts(wrap('one') + '\n第二题\n' + wrap('two'))
  assert.deepEqual(parts.filter(part => part.type === 'code').map(part => part.code), ['one', 'two'])
})
