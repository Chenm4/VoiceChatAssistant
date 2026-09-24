/**
 * Copy text in both secure browser contexts and restricted desktop/LAN WebViews.
 * navigator.clipboard is preferred, while execCommand keeps copy working when
 * Clipboard API permissions or HTTPS requirements are not satisfied.
 */
export async function copyText(text) {
  const value = String(text ?? '')

  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value)
      return
    } catch (error) {
      console.warn('Clipboard API 不可用，尝试兼容复制:', error)
    }
  }

  const textarea = document.createElement('textarea')
  textarea.value = value
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.top = '-9999px'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.focus()
  textarea.select()
  textarea.setSelectionRange(0, textarea.value.length)

  const copied = document.execCommand('copy')
  document.body.removeChild(textarea)

  if (!copied) {
    throw new Error('浏览器拒绝了剪贴板访问')
  }
}

function copyHtmlFallback(html) {
  const container = document.createElement('div')
  container.contentEditable = 'true'
  container.style.position = 'fixed'
  container.style.left = '-9999px'
  container.style.opacity = '0'
  container.innerHTML = html
  document.body.appendChild(container)

  const selection = window.getSelection()
  const range = document.createRange()
  range.selectNodeContents(container)
  selection.removeAllRanges()
  selection.addRange(range)
  const copied = document.execCommand('copy')
  selection.removeAllRanges()
  container.remove()

  if (!copied) throw new Error('浏览器拒绝了富文本剪贴板访问')
}

/**
 * Copy rich HTML with a plain-text representation for text-only targets.
 */
export async function copyRichContent(text, html) {
  const plainText = String(text ?? '')
  const richHtml = String(html ?? '')

  if (navigator.clipboard?.write && window.ClipboardItem) {
    try {
      const item = new ClipboardItem({
        'text/plain': new Blob([plainText], { type: 'text/plain' }),
        'text/html': new Blob([richHtml], { type: 'text/html' })
      })
      await navigator.clipboard.write([item])
      return
    } catch (error) {
      console.warn('富文本 Clipboard API 不可用，尝试兼容复制:', error)
    }
  }

  try {
    copyHtmlFallback(richHtml)
  } catch (error) {
    console.warn('富文本复制失败，回退到纯文本:', error)
    await copyText(plainText)
  }
}

/** Copy a captured image without replacing it with a text-only fallback. */
export async function copyImageBlob(blob) {
  if (!blob) throw new Error('没有可复制的截图')
  if (!navigator.clipboard?.write || !window.ClipboardItem) {
    throw new Error('当前浏览器不支持图片剪贴板')
  }

  const mimeType = blob.type || 'image/png'
  await navigator.clipboard.write([
    new ClipboardItem({ [mimeType]: blob })
  ])
}

export function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = () => reject(reader.error || new Error('图片读取失败'))
    reader.readAsDataURL(blob)
  })
}
