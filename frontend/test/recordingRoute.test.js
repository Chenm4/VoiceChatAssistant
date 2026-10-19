import test from 'node:test'
import assert from 'node:assert/strict'
import { recordingRoute, recordingModeName } from '../src/utils/recordingRoute.js'
const mic = { index: 2, name: 'Mic' }, usb = { index: 0, name: 'USB Sound Card' }
for (const source of ['microphone', 'usb']) {
  test(`${source} supports mixed, microphone-only and sound-card-only capture`, () => {
    const mixed = recordingRoute(source, 'mix', mic, usb)
    assert.equal(mixed.mix_inputs, true)
    assert.equal(mixed.input_device_index, source === 'usb' ? 0 : 2)
    assert.equal(mixed.standby_input_device_index, source === 'usb' ? 2 : 0)
    const micOnly = recordingRoute(source, 'microphone', mic, usb)
    assert.equal(micOnly.mix_inputs, false)
    assert.equal(micOnly.input_device_index, 2)
    const usbOnly = recordingRoute(source, 'usb', mic, usb)
    assert.equal(usbOnly.mix_inputs, false)
    assert.equal(usbOnly.input_device_index, 0)
    assert.equal(micOnly.input_source, source)
  })
}
test('defaults and same-device label remain clear', () => {
  assert.equal(recordingRoute('microphone', null, mic, usb).mix_inputs, true)
  assert.equal(recordingRoute('usb', null, mic, usb).mix_inputs, false)
  assert.equal(recordingModeName('mix', true), '单路（两项选择了同一设备）')
})
