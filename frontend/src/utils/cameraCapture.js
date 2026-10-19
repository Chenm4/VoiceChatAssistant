import { DisplayScreenCapture, waitForVideo } from './screenCapture.js'

// MediaDeviceInfo has no standard external/internal flag. Prefer recognizable
// external hardware, then other named hardware, before built-in/virtual cameras.
export function preferredCamera(devices, selectedId = '') {
  const cameras = devices.filter(device => device.kind === 'videoinput' && device.deviceId)
  const selected = cameras.find(device => device.deviceId === selectedId)
  if (selectedId) {
    if (!selected) throw new Error('所选摄像头已断开，请重新选择摄像头')
    return selected
  }
  const virtual = /virtual|obs|snap camera|manycam|虚拟/i
  const internal = /built[ -]?in|integrated|facetime|内置|内建|前置|后置|front|back|continuity|iphone/i
  const external = /usb|uvc|external|logitech|logi\b|brio|c920|c922|外接|外置/i
  return cameras.find(device => /ugreen.*2k|2k.*ugreen/i.test(device.label) && !virtual.test(device.label))
    || cameras.find(device => external.test(device.label) && !virtual.test(device.label))
    || cameras.find(device => device.label && !internal.test(device.label) && !virtual.test(device.label))
    || cameras.find(device => !virtual.test(device.label)) || cameras[0]
}

export class CameraCapture extends DisplayScreenCapture {
  constructor(onEnded, onDevices) {
    super(onEnded)
    this.onDevices = onDevices
    this.generation = 0
  }

  async selectSource(selectedId = '') {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('当前页面无法使用摄像头，请通过 localhost 或 HTTPS 打开')
    }
    this.stop()
    const generation = this.generation
    let stream
    let video
    const checkCancelled = () => {
      if (generation !== this.generation) throw new DOMException('已取消摄像头连接', 'AbortError')
    }
    const open = deviceId => navigator.mediaDevices.getUserMedia({
      audio: false,
      video: { ...(deviceId ? { deviceId: { exact: deviceId } } : {}),
        width: { ideal: 1920 }, height: { ideal: 1080 } }
    })
    try {
      let devices = await navigator.mediaDevices.enumerateDevices()
      checkCancelled()
      // Before permission, labels/IDs may be hidden. Open once to reveal them.
      const initial = devices.some(device => device.kind === 'videoinput' && device.label)
        ? preferredCamera(devices, selectedId) : null
      stream = await open(initial?.deviceId || selectedId)
      checkCancelled()
      devices = await navigator.mediaDevices.enumerateDevices()
      checkCancelled()
      this.onDevices?.(devices.filter(device => device.kind === 'videoinput'))
      const preferred = preferredCamera(devices, selectedId)
      if (preferred && stream.getVideoTracks()[0]?.getSettings().deviceId !== preferred.deviceId) {
        stream.getTracks().forEach(track => track.stop())
        stream = await open(preferred.deviceId)
        checkCancelled()
      }
      const track = stream.getVideoTracks()[0]
      if (!track) throw new Error('摄像头没有可用画面')
      video = document.createElement('video')
      video.muted = true
      video.playsInline = true
      video.srcObject = stream
      await video.play()
      await waitForVideo(video)
      checkCancelled()
      this.stream = stream
      this.video = video
      track.addEventListener('ended', () => {
        if (this.stream !== stream) return
        this.stop()
        this.onEnded?.()
      }, { once: true })
      return this.label
    } catch (error) {
      stream?.getTracks().forEach(track => track.stop())
      if (video) video.srcObject = null
      if (error.name === 'NotFoundError') throw new Error('未找到摄像头，请连接设备后重试')
      if (error.name === 'NotReadableError') throw new Error('无法打开摄像头，请检查是否被其他程序占用')
      throw error
    }
  }

  get label() {
    return this.stream?.getVideoTracks()[0]?.label || '摄像头'
  }

  stop() {
    this.generation++
    if (this.video) this.video.srcObject = null
    super.stop()
  }
}
