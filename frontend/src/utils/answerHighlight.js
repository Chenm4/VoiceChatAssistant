// Only accept a complete protocol block at the end of the visible answer.
export function parseAnswerHighlight(content) {
  const blocks = [...(content || '').matchAll(/(?:^|\n)```json[^\S\n]*\n([\s\S]*?)\n```/gi)]
  const match = blocks.at(-1)
  if (match && (content || '').slice(match.index + match[0].length).trim()) return []
  if (!match) return []
  try {
    const payload = JSON.parse(match[1])
    const answers = payload?.answer_highlight?.answers
    if (!Array.isArray(answers) || answers.length > 100) return []
    if (!answers.every(item => item && typeof item.question === 'string' && item.question.length <= 40
      && ((item.type === 'choice' && typeof item.answer === 'string' && /^[A-Z]{1,26}$/.test(item.answer)
        && new Set(item.answer).size === item.answer.length)
      || (item.type === 'boolean' && ['对', '错'].includes(item.answer))))) return []
    return answers
  } catch { return [] }
}

// Keep every model slot, including unfinished/empty models, in the card order.
export function answerHighlightModels(message) {
  if (!message) return []
  return (message.models || message.parallel_models || [message]).map((entry, index) => {
    const name = entry.model_info?.name || entry.model || ''
    const source = entry.model_info?.provider || entry.source_name || ''
    return {
      key: entry.model_key || entry.model_info?.id || `${source}::${name}::${index}`,
      label: [source, name].filter(Boolean).join(' · ') || `模型 ${index + 1}`,
      answers: entry.is_streaming ? [] : parseAnswerHighlight(entry.content)
    }
  })
}
