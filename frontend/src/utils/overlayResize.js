const clamp = (value, min, max) => Math.max(min, Math.min(max, value))

/** Resize from a corner while keeping its opposite corner fixed and visible. */
export function resizeOverlay(rect, corner, dx, dy, viewport, collapsed = false) {
  const minWidth = Math.min(280, viewport.width)
  const minHeight = Math.min(140, rect.height, viewport.height)
  const right = rect.x + rect.width
  const bottom = rect.y + rect.height
  const west = corner.includes('w'), north = corner.includes('n')
  const width = clamp(rect.width + (west ? -dx : dx), Math.min(minWidth, west ? right : viewport.width - rect.x), west ? right : viewport.width - rect.x)
  const height = collapsed ? rect.height : clamp(rect.height + (north ? -dy : dy), Math.min(minHeight, north ? bottom : viewport.height - rect.y), north ? bottom : viewport.height - rect.y)
  return { x: west ? right - width : rect.x, y: north && !collapsed ? bottom - height : rect.y, width, height }
}

/** Keep the complete measured panel visible after moving or content changes. */
export function fitOverlayRect(rect, viewport) {
  const width = Math.min(rect.width, viewport.width)
  const height = Math.min(rect.height, viewport.height)
  return { x: clamp(rect.x, 0, viewport.width - width),
    y: clamp(rect.y, 0, viewport.height - height), width, height }
}

/** Resize a floating panel while allowing its position outside the viewport. */
export function resizeFloatingOverlay(rect, corner, dx, dy, viewport, collapsed = false) {
  const west = corner.includes('w'), north = corner.includes('n')
  const width = clamp(rect.width + (west ? -dx : dx), Math.min(280, viewport.width), viewport.width)
  const height = collapsed ? rect.height : clamp(rect.height + (north ? -dy : dy),
    Math.min(140, rect.height, viewport.height), viewport.height)
  return { x: west ? rect.x + rect.width - width : rect.x,
    y: north && !collapsed ? rect.y + rect.height - height : rect.y, width, height }
}
