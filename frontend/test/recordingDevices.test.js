import test from 'node:test'
import assert from 'node:assert/strict'
import { preferredRecordingDevice } from '../src/utils/recordingDevices.js'
const devices = [{ index: 0, name: 'MacBook Pro麦克风' }, { index: 1, name: 'USB Camera Microphone' },
  { index: 3, name: 'USB PnP Sound Device' }]
test('defaults select built-in microphone and USB sound card, excluding webcam', () => {
  assert.equal(preferredRecordingDevice(devices, null, 'microphone').index, 0)
  assert.equal(preferredRecordingDevice(devices, null, 'usb').index, 3)
})
test('manual selections survive index changes and missing devices fall back to microphone', () => {
  assert.equal(preferredRecordingDevice(devices, { index: 8, name: 'USB PnP Sound Device' }, 'usb').index, 3)
  assert.equal(preferredRecordingDevice(devices, devices[1], 'usb').index, 1)
  assert.equal(preferredRecordingDevice([devices[0]], null, 'usb'), devices[0])
})

test('current USB Audio Device is preferred over system-default and virtual inputs', () => {
  const actual = [{ index: 0, name: 'USB Audio Device' }, { index: 1, name: 'MacBook Pro麦克风' },
    { index: 3, name: 'Iriun Webcam Audio' }, { index: 4, name: 'OrayVirtualAudioDevice' }]
  assert.equal(preferredRecordingDevice(actual, null, 'microphone').index, 1)
  assert.equal(preferredRecordingDevice(actual, null, 'usb').index, 0)
})
