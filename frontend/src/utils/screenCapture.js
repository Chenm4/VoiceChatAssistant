const MAX_CAPTURE_EDGE = 2200

function waitForVideo(video) {
  if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && video.videoWidth) {
    return Promise.resolve()
  }
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('等待共享画面超时')), 8000)
    video.addEventListener('loadeddata', () => {
      clearTimeout(timeout)
      resolve()
    }, { once: true })
    video.addEventListener('error', () => {
      clearTimeout(timeout)
      reject(new Error('无法读取共享画面'))
    }, { once: true })
  })
}

function canvasToBlob(canvas, type = 'image/webp', quality = 0.92) {
  return new Promise((resolve, reject) => {
    canvas.toBlob(blob => {
      if (blob) resolve(blob)
      else reject(new Error('生成截图失败'))
    }, type, quality)
  })
}

export class DisplayScreenCapture {
  constructor(onEnded) {
    this.stream = null
    this.video = null
    this.onEnded = onEnded
  }

  get connected() {
    return Boolean(this.stream?.getVideoTracks().some(track => track.readyState === 'live'))
  }

  get label() {
    const label = this.stream?.getVideoTracks()[0]?.label || ''
    if (!label || label.includes('media-stream://')) return '已选择窗口或标签页'
    return label
  }

  async selectSource() {
    if (!navigator.mediaDevices?.getDisplayMedia) {
      throw new Error('当前浏览器不支持窗口截图，请使用最新版 Chrome 或 Edge')
    }

    this.stop()
    const stream = await navigator.mediaDevices.getDisplayMedia({
      // Prefer the window picker while continuing to allow browser tabs.
      // The monitor option remains excluded to avoid capturing the full desktop.
      video: { displaySurface: 'window', frameRate: { ideal: 2, max: 5 } },
      audio: false,
      selfBrowserSurface: 'exclude',
      surfaceSwitching: 'include',
      monitorTypeSurfaces: 'exclude'
    })

    const track = stream.getVideoTracks()[0]
    const displaySurface = track?.getSettings?.().displaySurface
    if (displaySurface === 'monitor') {
      stream.getTracks().forEach(item => item.stop())
      throw new Error('请选择一个窗口或浏览器标签页，不要选择整个屏幕')
    }

    this.stream = stream
    this.video = document.createElement('video')
    this.video.muted = true
    this.video.playsInline = true
    this.video.srcObject = stream
    track.addEventListener('ended', () => {
      this.stream = null
      this.video = null
      this.onEnded?.()
    }, { once: true })
    await this.video.play()
    await waitForVideo(this.video)
    return this.label
  }

  async capture() {
    if (!this.connected || !this.video) {
      throw new Error('请先选择要截图的窗口或标签页')
    }
    await waitForVideo(this.video)
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))

    const sourceWidth = this.video.videoWidth
    const sourceHeight = this.video.videoHeight
    const scale = Math.min(1, MAX_CAPTURE_EDGE / Math.max(sourceWidth, sourceHeight))
    const width = Math.max(1, Math.round(sourceWidth * scale))
    const height = Math.max(1, Math.round(sourceHeight * scale))
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const context = canvas.getContext('2d', { alpha: false })
    context.drawImage(this.video, 0, 0, width, height)
    const [blob, clipboardBlob] = await Promise.all([
      canvasToBlob(canvas),
      // Chromium's image clipboard implementation is most reliable with PNG.
      canvasToBlob(canvas, 'image/png')
    ])
    return { blob, clipboardBlob, width, height }
  }

  stop() {
    const stream = this.stream
    this.stream = null
    this.video = null
    stream?.getTracks().forEach(track => track.stop())
  }
}
