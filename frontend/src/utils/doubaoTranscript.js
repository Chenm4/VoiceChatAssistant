import MarkdownIt from 'markdown-it'

const markdown = new MarkdownIt({ html: false, linkify: true, breaks: true })
export function renderDoubaoMarkdown(text) {
  return markdown.render(text || '')
}

// Follow the last line of content, rather than the blank space after it.
export function transcriptLatestTop(viewport, contentEnd) {
  if (!viewport || !contentEnd) return 0
  return Math.max(0, viewport.scrollTop + contentEnd.getBoundingClientRect().top
    - viewport.getBoundingClientRect().top - viewport.clientHeight + 16)
}
