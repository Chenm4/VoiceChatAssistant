// Bind the persisted question as soon as /chat returns, before answer tokens.
export function bindStreamingQuestion(messages, requestId, response) {
  const id = response.headers.get('X-User-Message-Id')
  const question = messages.find(message => message.role === 'user' && message.local_request_id === requestId)
  if (id && question) question.id = id
}

// Capture identity before aborting: stream cleanup may replace the message list.
export function editedQuestionReference(messages, messageId, messageIndex) {
  const question = messages.find(message => message.id && message.id === messageId)
    || (Number.isInteger(messageIndex) ? messages[messageIndex] : null)
  if (!question || question.role !== 'user') return null
  return { question, ordinal: messages.filter(message => message.role === 'user').indexOf(question) }
}

export async function resolveEditedQuestionId(reference, loadSession) {
  if (!reference) return null
  // The response headers may arrive while cancellation is being awaited.
  if (reference.question.id) return reference.question.id
  const session = await loadSession()
  const saved = (session.messages || []).filter(message => message.role === 'user')[reference.ordinal]
  if (!saved?.id || saved.content !== reference.question.content) return null
  reference.question.id = saved.id
  return saved.id
}

export function findEditedQuestionIndex(messages, reference, id) {
  const index = messages.findIndex(message => message.role === 'user' && message.id === id)
  if (index >= 0) return index
  const question = messages.filter(message => message.role === 'user')[reference.ordinal]
  if (!question || question.content !== reference.question.content) return -1
  question.id = id
  return messages.indexOf(question)
}
