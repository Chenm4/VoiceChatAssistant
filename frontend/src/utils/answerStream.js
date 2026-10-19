export function beginTargetedAnswer(messages, event) {
  const message = messages.find(item => item.id === event.message_id && item.role === 'assistant')
  if (!message) return null
  const keyOf = item => item.model_key || item.model_info?.id || `${item.model_info?.provider || item.source_name}::${item.model_info?.name || item.model}`
  const entries = message.models || message.parallel_models
  const target = entries ? entries.find(item => keyOf(item) === event.model_key)
    : keyOf(message) === event.model_key ? message : null
  if (!target) return null
  target.content = ''
  target.reasoning_content = ''
  target.is_streaming = true
  target.model_info = { ...target.model_info, reasoning_effort: event.reasoning_effort }
  return target
}

export function appendAnswerDelta(target, event) {
  if (!target) return
  const field = event.type === 'reasoning' ? 'reasoning_content' : 'content'
  target[field] = (target[field] || '') + (event.data || '')
}
