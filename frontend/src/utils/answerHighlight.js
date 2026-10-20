import { algorithmAnswerParts } from './algorithmAnswer.js'

// Only accept a complete protocol block at the end of the visible answer.
export function parseAnswerHighlight(content) {
  const blocks = [...(content || '').matchAll(/(?:^|\n)```json[^\S\n]*\n([\s\S]*?)\n```/gi)]
  const match = blocks.at(-1)
  if (match && (content || '').slice(match.index + match[0].length).trim()) return []
  if (!match) return []
  try {
    const payload = JSON.parse(match[1])
    // Providers sometimes omit the `answers` wrapper. Both forms carry the
    // same protocol; retain all item validation and final-block requirements.
    const highlight = payload?.answer_highlight
    const answers = Array.isArray(highlight) ? highlight : highlight?.answers
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

// Align model answers by question number, without merging separate messages.
export function answerHighlightPages(messages) {
  return messages.flatMap((message, messageIndex) => {
    if (message.role !== 'assistant') return []
    const models = answerHighlightModels(message)
    const codes = (message.models || message.parallel_models || [message]).map(entry => {
      const structured = algorithmAnswerParts(entry.content || '').filter(part => part.type === 'code')
      if (structured.length) return structured
      return [...(entry.content || '').matchAll(/(?:^|\n)```(java|python|javascript|typescript|cpp|c\+\+|c|go|rust)\s*\n([\s\S]*?)\n```/gi)]
        .filter(match => match[2].trim()).map(match => ({ language: match[1], code: match[2] }))
    })
    const codeCount = Math.max(0, ...codes.map(items => items.length))
    if (codeCount) return Array.from({ length: codeCount }, (_, index) => ({
      key: JSON.stringify([message.id ?? messageIndex, `code:${index}`]),
      messageIndex, question: `代码 ${index + 1}`, type: 'code',
      models: models.map((model, slot) => ({ ...model, answers: [], code: codes[slot][index] || null }))
    }))
    const questions = new Map()
    const indexed = models.map(model => {
      const occurrences = new Map()
      return new Map(model.answers.map((answer, index) => {
        const base = answer.question.trim() ? `question:${answer.question.trim()}` : `position:${index}`
        const occurrence = occurrences.get(base) || 0
        occurrences.set(base, occurrence + 1)
        const key = `${base}:${occurrence}`
        if (!questions.has(key)) questions.set(key, answer.question)
        return [key, answer]
      }))
    })
    return [...questions].map(([questionKey, question]) => ({
      key: JSON.stringify([message.id ?? messageIndex, questionKey]),
      messageIndex,
      question,
      models: models.map((model, index) => ({
        ...model,
        answers: indexed[index].has(questionKey) ? [indexed[index].get(questionKey)] : []
      }))
    }))
  })
}
