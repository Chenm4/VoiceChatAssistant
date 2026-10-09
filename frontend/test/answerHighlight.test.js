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
