class PcmCapture extends AudioWorkletProcessor {
  constructor() {
    super()
    this.ratio = sampleRate / 16000
    this.weight = 0
    this.total = 0
    this.samples = []
    this.port.onmessage = ({ data }) => {
      if (data === 'flush') {
        this.flush()
        this.port.postMessage({ type: 'flushed' })
      }
    }
  }

  flush() {
    if (!this.samples.length) return
    const buffer = new ArrayBuffer(this.samples.length * 2)
    const view = new DataView(buffer)
    this.samples.forEach((value, index) => view.setInt16(index * 2, value, true))
    this.samples = []
    this.port.postMessage({ type: 'pcm', buffer }, [buffer])
  }

  process(inputs) {
    const channels = inputs[0]
    if (!channels?.length) return true
    for (let index = 0; index < channels[0].length; index++) {
      const value = channels.reduce((sum, channel) => sum + channel[index], 0) / channels.length
      let remaining = 1
      while (remaining > 1e-8) {
        const take = Math.min(remaining, this.ratio - this.weight)
        this.total += value * take
        this.weight += take
        remaining -= take
        if (this.weight >= this.ratio - 1e-8) {
          const normalized = Math.max(-1, Math.min(1, this.total / this.ratio))
          this.samples.push(Math.round(normalized * (normalized < 0 ? 32768 : 32767)))
          this.total = 0
          this.weight = 0
          if (this.samples.length === 3200) this.flush()
        }
      }
    }
    return true
  }
}

registerProcessor('voice-pcm-capture', PcmCapture)
