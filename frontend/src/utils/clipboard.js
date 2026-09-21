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
