// Delay the single-key action so a double press never stops capture first.
export function createEscapeGesture({ single, double, delay = 350,
  schedule = setTimeout, cancel = clearTimeout }) {
  let pending = null
  function reset() {
    if (pending !== null) cancel(pending)
    pending = null
  }
  function handle(event) {
    if (event.isComposing || event.ctrlKey || event.altKey || event.metaKey || event.shiftKey) return false
    if (event.key !== 'Escape') return false
    if (event.repeat) return true
    if (pending !== null) {
      reset()
      double()
    } else {
      pending = schedule(() => {
        pending = null
        single()
      }, delay)
    }
    return true
  }
  return { handle, reset }
}
