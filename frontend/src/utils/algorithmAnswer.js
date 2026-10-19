// Parse only complete, explicitly named code cards; leave other JSON visible.
export function algorithmAnswerParts(content = '') {
  const parts = []
  let cursor = 0
  for (const match of content.matchAll(/(?:^|\n)```json[^\S\n]*\n([\s\S]*?)\n```/gi)) {
    let card
    try { card = JSON.parse(match[1])?.algorithm_answer } catch { continue }
    if (!card || typeof card.code !== 'string' || !card.code.trim()
      || typeof card.language !== 'string') continue
    if (match.index > cursor) parts.push({ type: 'markdown', text: content.slice(cursor, match.index) })
    parts.push({ type: 'code', code: card.code, language: card.language })
    cursor = match.index + match[0].length
  }
  if (cursor < content.length) parts.push({ type: 'markdown', text: content.slice(cursor) })
  return parts
}
