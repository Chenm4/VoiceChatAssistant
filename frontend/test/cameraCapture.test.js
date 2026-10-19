import test from 'node:test'
import assert from 'node:assert/strict'
import { CameraCapture, preferredCamera } from '../src/utils/cameraCapture.js'

const device = (deviceId, label) => ({ kind: 'videoinput', deviceId, label })
const internal = device('internal', 'FaceTime HD Camera (Built-in)')
const external = device('usb', 'USB Camera')
const virtual = device('virtual', 'OBS Virtual Camera')

test('prefers external hardware and honors manual choice; missing selection is explicit', () => {
  assert.equal(preferredCamera([internal, virtual, external]), external)
  assert.equal(preferredCamera([external, internal], 'internal'), internal)
  assert.equal(preferredCamera([virtual, internal]), internal)
  assert.equal(preferredCamera([]), undefined)
  assert.throws(() => preferredCamera([internal], 'missing'), /已断开/)
})

async function withMedia(run, { hidden = false, failPlayback = false, deny = false } = {}) {
  const originals = Object.fromEntries(['navigator', 'document', 'HTMLMediaElement'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]))
  const calls = []
  const tracks = []
  let enumerations = 0
  const mediaDevices = {
    async enumerateDevices() {
      enumerations++
      return hidden && enumerations === 1 ? [device('', '')] : [internal, external]
    },
    async getUserMedia(constraints) {
      calls.push(constraints)
      if (deny) throw new DOMException('Denied', 'NotAllowedError')
      const id = constraints.video.deviceId?.exact || 'internal'
      const track = new EventTarget()
      Object.assign(track, { readyState: 'live', label: id === 'usb' ? 'USB Camera' : 'FaceTime',
        getSettings: () => ({ deviceId: id }), stop() { this.readyState = 'ended' } })
      tracks.push(track)
      return { getTracks: () => [track], getVideoTracks: () => [track] }
    }
  }
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { mediaDevices } })
  Object.defineProperty(globalThis, 'HTMLMediaElement', { configurable: true, value: { HAVE_CURRENT_DATA: 2 } })
  Object.defineProperty(globalThis, 'document', { configurable: true, value: {
    createElement: () => ({ readyState: 2, videoWidth: 1920,
      play: async () => { if (failPlayback) throw new Error('playback failed') } })
  } })
  try { await run({ calls, tracks, mediaDevices }) }
  finally {
    for (const [key, descriptor] of Object.entries(originals)) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor)
      else delete globalThis[key]
    }
  }
}

test('opens external camera directly without screen sharing or audio, and disconnects', async () => {
  await withMedia(async ({ calls, tracks }) => {
    let listed
    const capture = new CameraCapture(null, devices => { listed = devices })
    assert.equal(await capture.selectSource(), 'USB Camera')
    assert.equal(calls.length, 1)
    assert.equal(calls[0].video.deviceId.exact, 'usb')
    assert.equal(calls[0].audio, false)
    assert.equal(listed.length, 2)
    assert.equal(capture.connected, true)
    capture.stop()
    assert.equal(capture.connected, false)
    assert.ok(tracks.every(track => track.readyState === 'ended'))
  })
})

test('after first permission reveals labels, releases bootstrap camera and selects external', async () => {
  await withMedia(async ({ calls, tracks }) => {
    const capture = new CameraCapture()
    await capture.selectSource()
    assert.equal(calls.length, 2)
    assert.equal(calls[1].video.deviceId.exact, 'usb')
    assert.equal(tracks[0].readyState, 'ended')
    capture.stop()
  }, { hidden: true })
})

test('playback failure releases camera tracks', async () => {
  await withMedia(async ({ tracks }) => {
    const capture = new CameraCapture()
    await assert.rejects(capture.selectSource(), /playback failed/)
    assert.equal(capture.connected, false)
    assert.ok(tracks.every(track => track.readyState === 'ended'))
  }, { failPlayback: true })
})

test('permission denial does not fall back to screen sharing', async () => {
  await withMedia(async ({ calls }) => {
    const capture = new CameraCapture()
    await assert.rejects(capture.selectSource(), { name: 'NotAllowedError' })
    assert.equal(calls.length, 1)
    assert.equal(capture.connected, false)
  }, { deny: true })
})

test('disconnect while permission is pending releases the late stream', async () => {
  await withMedia(async ({ mediaDevices, tracks }) => {
    const original = mediaDevices.getUserMedia
    let release
    let opened
    const waiting = new Promise(resolve => { opened = resolve })
    mediaDevices.getUserMedia = async constraints => {
      const stream = await original(constraints)
      opened()
      await new Promise(resolve => { release = resolve })
      return stream
    }
    const capture = new CameraCapture()
    const selecting = capture.selectSource()
    await waiting
    capture.stop()
    release()
    await assert.rejects(selecting, { name: 'AbortError' })
    assert.ok(tracks.every(track => track.readyState === 'ended'))
    assert.equal(capture.connected, false)
  })
})

test('unplugging active camera updates connected state', async () => {
  await withMedia(async ({ tracks }) => {
    let ended = false
    const capture = new CameraCapture(() => { ended = true })
    await capture.selectSource('internal')
    tracks[0].dispatchEvent(new Event('ended'))
    assert.equal(ended, true)
    assert.equal(capture.connected, false)
  })
})

test('UGREEN Camera 2K wins over other external cameras unless manually overridden', () => {
  const ugreen = device('ugreen', 'UGREEN Camera 2K (0c45:636f)')
  assert.equal(preferredCamera([internal, external, ugreen]), ugreen)
  assert.equal(preferredCamera([external, ugreen], 'usb'), external)
  assert.equal(preferredCamera([internal, external]), external)
})
