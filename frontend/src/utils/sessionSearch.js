// Keep only searchable text in memory; never retain session configuration or attachments.
export function messageText(messages = []) {
  return messages.filter(message => ['user', 'assistant'].includes(message.role)).flatMap(message => [
    message.content,
    ...(message.parallel_models || message.models || []).map(model => model.content)
  ]).filter(text => typeof text === 'string' && text.trim()).join('\n')
}

export function matchSnippet(text, query) {
  const normalized = text.replace(/\s+/g, ' ')
  const index = normalized.toLocaleLowerCase().indexOf(query.toLocaleLowerCase())
  if (index < 0) return null
  const start = Math.max(0, index - 24)
  const end = Math.min(normalized.length, index + query.length + 65)
  return `${start ? '…' : ''}${normalized.slice(start, end)}${end < normalized.length ? '…' : ''}`
}

export function createSessionSearch(fetchSession) {
  const cache = new Map()
  return async function search(sessions, query, signal) {
    const needle = query.trim()
    if (!needle) return { matches: [], failures: 0 }
    const ids = new Set(sessions.map(session => session.id))
    for (const id of cache.keys()) if (!ids.has(id)) cache.delete(id)
    const results = new Array(sessions.length)
    let next = 0
    let failures = 0
    async function worker() {
      while (next < sessions.length && !signal?.aborted) {
        const index = next++
        const session = sessions[index]
        if (session.title.toLocaleLowerCase().includes(needle.toLocaleLowerCase())) {
          results[index] = { ...session, matchType: 'title', snippet: '' }
          continue
        }
        try {
          const revision = `${session.updated_at}:${session.message_count ?? session.messages?.length}`
          let cached = cache.get(session.id)
          if (!cached || cached.revision !== revision) {
            const detail = await fetchSession(session.id, signal)
            if (signal?.aborted) return
            cached = { revision, text: messageText(detail.messages) }
            cache.set(session.id, cached)
          }
          const snippet = matchSnippet(cached.text, needle)
          if (snippet !== null) results[index] = { ...session, matchType: 'content', snippet }
        } catch (error) {
          if (signal?.aborted) return
          failures++
        }
      }
    }
    await Promise.all(Array.from({ length: Math.min(4, sessions.length) }, worker))
    return { matches: results.filter(Boolean), failures }
  }
}
