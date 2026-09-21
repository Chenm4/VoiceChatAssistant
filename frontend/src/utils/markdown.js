/**
 * Markdown 渲染工具
 */

import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import { copyText } from './clipboard'

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true
})

// 自定义代码块渲染规则（避免嵌套问题）
md.renderer.rules.fence = function (tokens, idx) {
  const token = tokens[idx]
  const code = token.content
  const lang = token.info.trim()
  
  let highlighted
  if (lang && hljs.getLanguage(lang)) {
    try {
      highlighted = hljs.highlight(code, { language: lang, ignoreIllegals: true }).value
    } catch (__) {
      highlighted = md.utils.escapeHtml(code)
    }
  } else {
    highlighted = md.utils.escapeHtml(code)
  }
  
  return `<div class="code-block-wrapper">
  <button class="copy-button" onclick="copyCode(event)"><i class="fas fa-copy"></i></button>
  <pre class="hljs"><code>${highlighted}</code></pre>
</div>`
}

/**
 * 渲染 Markdown
 * @param {string} content - Markdown 内容
 * @returns {string} - HTML 字符串
 */
export function renderMarkdown(content) {
  if (!content) return ''
  return md.render(content)
}

/**
 * 复制代码到剪贴板
 * 这个函数会被添加到 window 对象，供 HTML 中的按钮调用
 */
window.copyCode = async function(event) {
  const button = event.currentTarget
  const codeBlock = button.parentElement.querySelector('code')
  const text = codeBlock.textContent
  
  try {
    await copyText(text)
    const originalHTML = button.innerHTML
    button.innerHTML = '<i class="fas fa-check"></i>'
    button.style.color = '#10b981'
    setTimeout(() => {
      button.innerHTML = originalHTML
      button.style.color = ''
    }, 1500)
  } catch (error) {
    console.error('复制失败:', error)
  }
}

export default md
