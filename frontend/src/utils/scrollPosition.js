export function captureReadingPosition(scroller) {
  if (!scroller) return null
  const top = scroller.getBoundingClientRect().top
  const anchor = [...scroller.querySelectorAll('[data-message-index]')]
    .find(element => element.getBoundingClientRect().bottom > top)
  return { top: scroller.scrollTop, id: anchor?.getAttribute('data-message-id') || null,
    index: anchor?.getAttribute('data-message-index'),
    offset: anchor ? anchor.getBoundingClientRect().top - top : 0 }
}
export function restoreReadingPosition(scroller, position) {
  if (!scroller || !position) return
  // An answer refresh may change message indices. Match the same message when
  // possible; falling back to the old numeric scroll position is safer than
  // jumping to a different message that now happens to share its index.
  const anchor = position.id
    ? [...scroller.querySelectorAll('[data-message-id]')].find(element => element.getAttribute('data-message-id') === position.id)
    : null
  scroller.scrollTop = anchor ? scroller.scrollTop + anchor.getBoundingClientRect().top
    - scroller.getBoundingClientRect().top - position.offset : position.top
}
