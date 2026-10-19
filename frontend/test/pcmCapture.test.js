import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

function processor(sampleRate) {
  let Processor
  const packets = []
  vm.runInNewContext(readFileSync(new URL('../src/utils/pcmCapture.worklet.js', import.meta.url), 'utf8'), {
    sampleRate, AudioWorkletProcessor: class { constructor() { this.port = { postMessage: packet => packets.push(packet) } } },
    registerProcessor: (name, value) => { Processor = value },
  })
  return { capture: new Processor(), packets }
}

test('44.1kHz and 48kHz inputs produce mono 16kHz PCM16 without block-boundary drift', () => {
  for (const rate of [44100, 48000]) {
    const { capture, packets } = processor(rate)
    for (let offset = 0; offset < rate; offset += 128) {
      const count = Math.min(128, rate - offset)
      capture.process([[new Float32Array(count).fill(1), new Float32Array(count).fill(-1)]])
    }
    capture.port.onmessage({ data: 'flush' })
    const audio = packets.filter(packet => packet.type === 'pcm')
    assert.equal(audio.reduce((sum, packet) => sum + packet.buffer.byteLength, 0), 32000)
    assert.ok(audio.every(packet => new Uint8Array(packet.buffer).every(value => value === 0)))
    assert.equal(packets.at(-1).type, 'flushed')
  }
})

test('flush preserves short tail and samples use clipped little-endian PCM', () => {
  const { capture, packets } = processor(16000)
  capture.process([[new Float32Array([2, -2, .5])]])
  assert.equal(packets.length, 0)
  capture.port.onmessage({ data: 'flush' })
  const data = new DataView(packets[0].buffer)
  assert.equal(data.byteLength, 6)
  assert.equal(data.getInt16(0, true), 32767)
  assert.equal(data.getInt16(2, true), -32768)
  assert.equal(data.getInt16(4, true), 16384)
})
