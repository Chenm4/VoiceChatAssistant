import { currentUsername } from './auth.js'
/** Text output for explicitly submitted typed questions or completed recordings. */
export class DoubaoRealtime {
  constructor(onMessage, onClose) {
    this.onMessage = onMessage
    this.onClose = onClose
    this.closed = false
  }
  start(options) {
    const url = new URL('/api/doubao-realtime/ws', window.location.href)
    url.searchParams.set('workspace_user', currentUsername())
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    this.socket = new WebSocket(url)
    this.socket.onopen = () => { if (!this.closed) this.socket.send(JSON.stringify({ type: 'start', ...options })) }
    this.socket.onmessage = ({ data }) => {
      if (this.closed || typeof data !== 'string') return
      const message = JSON.parse(data)
      this.onMessage(message)
      if (message.type === 'complete' || message.type === 'error') this.close()
    }
    this.socket.onerror = () => {
      this.onMessage({ type: 'error', message: '豆包连接异常，请检查后端服务' })
      this.close()
    }
    this.socket.onclose = () => this.close()
  }
  close() {
    if (this.closed) return
    this.closed = true
    if (this.socket?.readyState === WebSocket.OPEN) this.socket.send(JSON.stringify({ type: 'stop' }))
    this.socket?.close()
    this.onClose()
  }
}
