import test from 'node:test'
import assert from 'node:assert/strict'
import { parseAnswerHighlight } from '../src/utils/answerHighlight.js'
const wrap = answers => '分析完成。\n```json\n' + JSON.stringify({ answer_highlight: { answers } }) + '\n```'
test('final single, multiple choice and boolean answers', () => {
  const answers = [{ question: '1', type: 'choice', answer: 'AC' }, { question: '2', type: 'boolean', answer: '错' }]
  assert.deepEqual(parseAnswerHighlight(wrap(answers)), answers)
})
test('reject incomplete, unrelated, invalid or nonfinal JSON', () => {
  const valid = wrap([{ question: '', type: 'choice', answer: 'A' }])
  for (const text of [valid.slice(0, -1), valid + '\n继续分析', '```json\n{"answer":"A"}\n```', wrap([{ question: '', type: 'choice', answer: '<script>' }]), wrap([{ question: '', type: 'boolean', answer: true }])]) assert.deepEqual(parseAnswerHighlight(text), [])
  assert.deepEqual(parseAnswerHighlight(wrap([])), [])
})

test('ignore earlier JSON examples and accept only the final protocol', () => {
  const answers = [{ question: '', type: 'choice', answer: 'B' }]
  assert.deepEqual(parseAnswerHighlight('```json\n{"example":true}\n```\n' + wrap(answers)), answers)
})

test('parallel model slots stay in card order even when only the right model completes', async () => {
  const { answerHighlightModels } = await import('../src/utils/answerHighlight.js')
  const message = { models: [
    { model_key: 'left', model_info: { name: 'same-model', provider: '左侧来源' }, content: '', is_streaming: true },
    { model_key: 'right', model_info: { name: 'same-model', provider: '右侧来源' }, content: wrap([{ question: '12', type: 'choice', answer: 'B' }]) }
  ] }
  let models = answerHighlightModels(message)
  assert.equal(models.length, 2)
  assert.deepEqual(models[0].answers, [])
  assert.equal(models[1].answers[0].answer, 'B')
  assert.equal(models[1].answers[0].question, '12')
  assert.notEqual(models[0].label, models[1].label)
  message.models[0].is_streaming = false
  message.models[0].content = wrap([{ question: '12', type: 'choice', answer: 'A' }, { question: '13', type: 'boolean', answer: '对' }])
  models = answerHighlightModels(message)
  assert.deepEqual(models.map(model => model.key), ['left', 'right'])
  assert.equal(models[0].answers.length, 2)
  assert.equal(models[1].answers[0].answer, 'B')
  assert.deepEqual(answerHighlightModels({ parallel_models: message.models }), models)
})

test('history navigation keeps messages separate and aligns parallel answers by number', async () => {
  const { answerHighlightPages } = await import('../src/utils/answerHighlight.js')
  const answer = (question, value = 'A') => ({ question, type: 'choice', answer: value })
  const messages = [
    { role: 'user', content: '题目' },
    { id: 'first', role: 'assistant', content: wrap([answer('1'), answer('2')]) },
    { role: 'assistant', models: [
      { content: wrap([answer('2'), answer('3')]) },
      { content: wrap([answer('3', 'B'), answer('2', 'C'), answer('4')]) }
    ] },
    { role: 'user', content: '新题目' }
  ]
  const pages = answerHighlightPages(messages)
  assert.deepEqual(pages.map(page => page.question), ['1', '2', '2', '3', '4'])
  assert.deepEqual(pages.map(page => page.messageIndex), [1, 1, 2, 2, 2])
  assert.equal(new Set(pages.map(page => page.key)).size, 5)
  assert.deepEqual(pages[2].models.map(model => model.answers[0].answer), ['A', 'C'])
  assert.deepEqual(pages[4].models[0].answers, [])
})

test('late models preserve question keys; streaming and malformed answers are excluded', async () => {
  const { answerHighlightPages } = await import('../src/utils/answerHighlight.js')
  const right = { content: wrap([{ question: '12', type: 'choice', answer: 'B' }]) }
  const left = { content: right.content, is_streaming: true }
  const messages = [{ id: 'reply', role: 'assistant', models: [left, right] }]
  const before = answerHighlightPages(messages)
  assert.deepEqual(before[0].models[0].answers, [])
  left.is_streaming = false
  assert.equal(answerHighlightPages(messages)[0].key, before[0].key)
  assert.equal(answerHighlightPages(messages)[0].models[0].answers[0].answer, 'B')
  assert.deepEqual(answerHighlightPages([{ role: 'assistant', content: 'invalid' }]), [])
})

test('unnumbered and repeated question numbers remain individually reachable', async () => {
  const { answerHighlightPages } = await import('../src/utils/answerHighlight.js')
  const answers = ['', '', '1', '1'].map(question => ({ question, type: 'boolean', answer: '对' }))
  const pages = answerHighlightPages([{ role: 'assistant', content: wrap(answers) }])
  assert.equal(pages.length, 4)
  assert.equal(new Set(pages.map(page => page.key)).size, 4)
})

test('both model codes automatically share a page, including ordinary code fences', async () => {
  const { answerHighlightPages } = await import('../src/utils/answerHighlight.js')
  const json = '```json\n' + JSON.stringify({ algorithm_answer: { language: 'java', code: 'class Main {}' } }) + '\n```'
  const messages = [{ id: 'code', role: 'assistant', models: [
    { model_key: 'left', content: json },
    { model_key: 'right', content: '```java\nclass Other {}\n```' }
  ] }]
  const [page] = answerHighlightPages(messages)
  assert.equal(page.type, 'code')
  assert.deepEqual(page.models.map(model => model.code.code), ['class Main {}', 'class Other {}'])
  messages[0].models[1].content = ''
  const [pending] = answerHighlightPages(messages)
  assert.equal(pending.models.length, 2)
  assert.equal(pending.models[1].code, null)
  assert.equal(pending.key, page.key)
})


test('accept direct answer_highlight arrays from saved provider responses', async () => {
  const { answerHighlightPages } = await import('../src/utils/answerHighlight.js')
  const answers = [{ question: '', type: 'choice', answer: 'A' }]
  const content = '正确选项是 A。\n```json\n' + JSON.stringify({ answer_highlight: answers }) + '\n```'
  assert.deepEqual(parseAnswerHighlight(content), answers)
  const pages = answerHighlightPages([{ id: 'saved', role: 'assistant', content }])
  assert.equal(pages[0].models[0].answers[0].answer, 'A')
  assert.deepEqual(parseAnswerHighlight(content + '\n后续分析'), [])
  assert.deepEqual(parseAnswerHighlight('```json\n' + JSON.stringify({ answer_highlight: [{question: '', type: 'choice', answer: '<script>'}] }) + '\n```'), [])
})
