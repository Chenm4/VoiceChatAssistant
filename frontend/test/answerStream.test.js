import test from 'node:test'
import assert from 'node:assert/strict'
import { beginTargetedAnswer, appendAnswerDelta } from '../src/utils/answerStream.js'

test('targeted rerun streams reasoning and answer into only the matching card before done', () => {
  const sibling = { model_key: 'p::b', content: 'keep' }
  const messages = [{ id: 'a', role: 'assistant', parallel_models: [{model_key:'p::a', content:'old'}, sibling] }]
  const target = beginTargetedAnswer(messages, {message_id:'a', model_key:'p::a', reasoning_effort:'medium'})
  assert.equal(target.content, '')
  assert.equal(target.is_streaming, true)
  appendAnswerDelta(target, {type:'reasoning', data:'step 1'})
  appendAnswerDelta(target, {type:'reasoning', data:' step 2'})
  appendAnswerDelta(target, {type:'content', data:'answer'})
  assert.equal(messages[0].parallel_models[0].reasoning_content, 'step 1 step 2')
  assert.equal(messages[0].parallel_models[0].content, 'answer')
  assert.equal(sibling.content, 'keep')
})
test('single answers and stale message IDs', () => {
  const messages = [{id:'a', role:'assistant',content:'old',model_info:{name:'m',provider:'p'}}]
  assert.equal(beginTargetedAnswer(messages,{message_id:'missing', model_key:'p::m'}), null)
  assert.equal(messages[0].content,'old')
  const target=beginTargetedAnswer(messages,{message_id:'a',model_key:'p::m',reasoning_effort:'high'})
  appendAnswerDelta(target,{type:'content',data:'new'})
  assert.equal(messages[0].content,'new')
  assert.equal(messages[0].model_info.reasoning_effort,'high')
})
