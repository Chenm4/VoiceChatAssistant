import test from 'node:test'
import assert from 'node:assert/strict'
import { bindStreamingQuestion, editedQuestionReference, resolveEditedQuestionId, findEditedQuestionIndex } from '../src/utils/streamingQuestion.js'

test('headers assign real IDs to ordinary and parallel capture questions before answer completion', () => {
  const messages = [{ role: 'user', local_request_id: 'text' }, { role: 'assistant' },
    { role: 'user', local_request_id: 'capture' }]
  for (const requestId of ['text', 'capture']) {
    bindStreamingQuestion(messages, requestId, { headers: new Headers({ 'X-User-Message-Id': `saved-${requestId}` }) })
  }
  assert.equal(messages[0].id, 'saved-text')
  assert.equal(messages[2].id, 'saved-capture')
  assert.equal(messages[1].id, undefined)
})

test('edit before headers arrive resolves persisted question after cancellation, with duplicate text', async () => {
  const messages = [{ role: 'user', id: 'old', content: 'same' }, { role: 'assistant', content: 'old answer' },
    { role: 'user', content: 'same' }, { role: 'assistant', content: 'unfinished' }]
  const reference = editedQuestionReference(messages, undefined, 2)
  const refreshed = [{ role: 'user', id: 'old', content: 'same' }, { role: 'assistant' },
    { role: 'user', id: 'new', content: 'same' }]
  const id = await resolveEditedQuestionId(reference, async () => ({ messages: refreshed }))
  assert.equal(id, 'new')
  assert.equal(findEditedQuestionIndex(refreshed, reference, id), 2)
  assert.equal(messages[2].id, 'new')
})

test('uses ID arriving during interruption without loading another session', async () => {
  const messages = [{ role: 'user', content: 'question' }]
  const reference = editedQuestionReference(messages, undefined, 0)
  messages[0].id = 'real-id'
  assert.equal(await resolveEditedQuestionId(reference, () => assert.fail('unexpected refresh')), 'real-id')
})

test('missing or changed persisted questions cannot regenerate another question', async () => {
  const messages = [{ role: 'user', content: 'unsaved' }]
  const reference = editedQuestionReference(messages, undefined, 0)
  assert.equal(await resolveEditedQuestionId(reference, async () => ({ messages: [] })), null)
  assert.equal(await resolveEditedQuestionId(reference, async () => ({ messages: [{ role: 'user', id: 'other', content: 'other' }] })), null)
  assert.equal(editedQuestionReference([{ role: 'assistant' }], undefined, 0), null)
})
