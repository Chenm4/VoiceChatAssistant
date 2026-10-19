export function clipboardImages(clipboardData) {
  const images = Array.from(clipboardData?.items || [])
    .filter(item => item.kind === 'file' && item.type.startsWith('image/'))
    .map(item => item.getAsFile()).filter(Boolean)
  return images.length ? images : Array.from(clipboardData?.files || []).filter(file => file.type.startsWith('image/'))
}

export async function uploadChatImage(file, sessionId) {
  const form = new FormData()
  form.append('session_id', sessionId)
  form.append('screenshot', file, file.name || 'clipboard.png')
  const response = await fetch('/api/attachments/screenshots', { method: 'POST', body: form })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || `图片上传失败 (${response.status})`)
  }
  return response.json()
}
