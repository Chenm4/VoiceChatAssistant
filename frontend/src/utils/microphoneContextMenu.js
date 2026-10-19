/** Capture at window level so teleported overlays and existing menus behave alike. */
export function installMicrophoneContextMenu(target, toggle, { getAction = () => 'record', capturePhoto } = {}) {
  const capture = { capture: true }
  const runRightClickAction = () => {
    if (getAction() === 'photo') capturePhoto?.()
    else toggle()
  }
  const blockSecondaryDown = event => {
    if (event.button === 2 || (event.button === 0 && event.ctrlKey)) {
      // Do not let draggable controls turn a right-click into a second toggle.
      event.stopImmediatePropagation()
    }
  }
  const onContextMenu = event => {
    if (event.target?.closest?.('.user-guide-dialog')) return
    event.preventDefault()
    event.stopImmediatePropagation()
    runRightClickAction()
  }
  const onEnter = event => {
    if (event.key !== 'Enter' || event.repeat || event.isComposing || event.keyCode === 229 ||
        event.ctrlKey || event.altKey || event.metaKey || event.shiftKey ||
        event.target?.closest?.('input, textarea, select, [contenteditable=""], [contenteditable="true"], [role="textbox"], [role="dialog"], .el-overlay')) return
    event.preventDefault()
    event.stopImmediatePropagation()
    runRightClickAction()
  }
  target.addEventListener('pointerdown', blockSecondaryDown, capture)
  target.addEventListener('mousedown', blockSecondaryDown, capture)
  target.addEventListener('contextmenu', onContextMenu, capture)
  target.addEventListener('keydown', onEnter, capture)
  return () => {
    target.removeEventListener('pointerdown', blockSecondaryDown, capture)
    target.removeEventListener('mousedown', blockSecondaryDown, capture)
    target.removeEventListener('contextmenu', onContextMenu, capture)
    target.removeEventListener('keydown', onEnter, capture)
  }
}
