import { privateUrl } from './auth.js'

export async function browserRecordingDevices() {
  if (!navigator.mediaDevices?.getUserMedia) throw new Error('请使用支持麦克风的浏览器，通过 HTTPS 访问')
  const devices = (await navigator.mediaDevices.enumerateDevices())
    .filter(device => device.kind === 'audioinput' && device.deviceId !== 'communications')
    .map((device, index) => ({ index: device.deviceId, name: device.label || `麦克风 ${index + 1}` }))
  return { devices, default_index: devices.find(device => device.index === 'default')?.index ?? devices[0]?.index ?? null }
}

export class BrowserRecording {
  constructor(onError) {
    this.onError = onError
    this.streams = []
    this.sources = []
    this.pending = []
    this.inFlight = 0
    this.closed = false
    this.stopping = false
    this.deviceRevision = 0
  }

  async openInputs(route) {
    const requested = [route.input_device_index || 'default']
    if (route.mix_inputs && route.standby_input_device_index && !requested.includes(route.standby_input_device_index)) {
      requested.push(route.standby_input_device_index)
    }
    const streams = []
    try {
      for (const deviceId of requested) {
        streams.push(await navigator.mediaDevices.getUserMedia({ audio: {
          deviceId: deviceId === 'default' ? undefined : { exact: deviceId },
          channelCount: 1, echoCancellation: true, noiseSuppression: true,
        } }))
      }
      return streams
    } catch (error) {
      streams.forEach(stream => stream.getTracks().forEach(track => track.stop()))
      if (error.name === 'NotAllowedError') throw new Error('麦克风权限被拒绝，请在浏览器中允许此网站使用麦克风')
      throw error
    }
  }

  connectInputs(streams) {
    this.sources.forEach(source => source.disconnect())
    this.streams.forEach(stream => stream.getTracks().forEach(track => track.stop()))
    this.streams = streams
    this.sources = []
    for (const stream of streams) {
      const source = this.context.createMediaStreamSource(stream)
      const gain = this.context.createGain()
      gain.gain.value = 1 / streams.length
      source.connect(gain).connect(this.worklet)
      this.sources.push(source, gain)
      stream.getAudioTracks().forEach(track => {
        track.onended = () => this.fail(new Error('麦克风已断开，请重新选择设备'))
      })
    }
  }

  async start(route) {
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('请使用支持麦克风的浏览器，通过 HTTPS 访问')
      const inputs = await this.openInputs(route)
      if (this.closed) {
        inputs.forEach(stream => stream.getTracks().forEach(track => track.stop()))
        throw new Error('录音已取消')
      }
      this.streams = inputs
      this.context = new AudioContext()
      await this.context.audioWorklet.addModule(new URL('./pcmCapture.worklet.js', import.meta.url))
      if (this.closed) throw new Error('录音已取消')
      this.worklet = new AudioWorkletNode(this.context, 'voice-pcm-capture')
      this.worklet.port.onmessage = ({ data }) => {
        if (data.type === 'flushed') return this.flushResolve?.()
        if (this.closed) return
        this.pending.push(data.buffer)
        if (this.pending.length > 10) return this.fail(new Error('音频上传过慢，录音已停止，请检查网络'))
        this.sendPending()
      }
      const url = new URL(privateUrl('/api/recording/browser'), window.location.origin)
      url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
      this.socket = new WebSocket(url)
      await new Promise((resolve, reject) => {
        this.startReject = reject
        this.startTimer = setTimeout(() => reject(new Error('录音服务连接超时')), 20000)
        this.socket.onmessage = ({ data }) => {
          const message = JSON.parse(data)
          if (message.type === 'ready') {
            clearTimeout(this.startTimer)
            this.startReject = null
            resolve()
          } else if (message.type === 'ack') {
            this.inFlight--
            this.sendPending()
          } else if (message.type === 'stopped') {
            this.stopResolve?.(message)
          } else if (message.type === 'error') {
            this.fail(new Error(message.message))
          }
        }
        this.socket.onerror = () => this.fail(new Error('录音连接失败，请检查网络并重新登录'))
        this.socket.onclose = () => { if (!this.closed && !this.completed) this.fail(new Error('录音连接已断开')) }
      })
      const streams = this.streams
      this.streams = []
      this.connectInputs(streams)
      const silence = this.context.createGain()
      silence.gain.value = 0
      this.worklet.connect(silence).connect(this.context.destination)
      await this.context.resume()
      return { success: true }
    } catch (error) {
      await this.dispose()
      throw error
    }
  }

  sendPending() {
    while (this.socket?.readyState === WebSocket.OPEN && this.inFlight < 4 && this.pending.length) {
      this.socket.send(this.pending.shift())
      this.inFlight++
    }
  }

  async switchInput(route) {
    const revision = ++this.deviceRevision
    const streams = await this.openInputs(route)
    if (this.closed || this.stopping || revision !== this.deviceRevision) {
      streams.forEach(stream => stream.getTracks().forEach(track => track.stop()))
      throw new Error('录音已结束')
    }
    this.connectInputs(streams)
    return { success: true }
  }

  async stop(finalize = true) {
    this.stopping = true
    try {
      if (this.closed) throw new Error('录音连接已断开')
      await new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error('音频尾包处理超时')), 3000)
        this.flushResolve = () => { clearTimeout(timer); resolve() }
        this.sources.forEach(source => source.disconnect())
        this.worklet.port.postMessage('flush')
      })
      await this.context.suspend()
      const deadline = Date.now() + 10000
      while (this.pending.length || this.inFlight) {
        if (this.closed || Date.now() > deadline) throw new Error('音频上传未完成，请检查网络')
        await new Promise(resolve => setTimeout(resolve, 20))
      }
      return await new Promise((resolve, reject) => {
        this.stopTimer = setTimeout(() => reject(new Error('等待识别结果超时')), 60000)
        this.stopReject = reject
        this.stopResolve = result => { this.completed = true; resolve(result) }
        this.socket.send(JSON.stringify({ type: 'stop', finalize }))
      })
    } finally {
      await this.dispose()
    }
  }

  fail(error) {
    if (this.closed) return
    this.startReject?.(error)
    this.stopReject?.(error)
    this.onError?.(error)
    void this.dispose()
  }

  async dispose() {
    if (this.closed) return
    this.closed = true
    this.startReject?.(new Error('录音已取消'))
    this.stopReject?.(new Error('录音已取消'))
    clearTimeout(this.startTimer)
    clearTimeout(this.stopTimer)
    this.sources.forEach(source => source.disconnect())
    this.streams.forEach(stream => stream.getTracks().forEach(track => track.stop()))
    this.worklet?.disconnect()
    this.socket?.close()
    if (this.context && this.context.state !== 'closed') await this.context.close()
  }
}
