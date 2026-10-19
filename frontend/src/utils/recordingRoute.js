export const RECORDING_MODES = ['mix', 'microphone', 'usb']

export function recordingRoute(source, mode, microphone, soundCard) {
  const selectedMode = RECORDING_MODES.includes(mode) ? mode : source === 'usb' ? 'usb' : 'mix'
  const primary = selectedMode === 'mix'
    ? (source === 'usb' ? soundCard : microphone)
    : (selectedMode === 'usb' ? soundCard : microphone)
  const standby = selectedMode === 'mix'
    ? (source === 'usb' ? microphone : soundCard)
    : (selectedMode === 'usb' ? microphone : soundCard)
  return {
    input_device_index: primary?.index ?? null,
    input_device_name: primary?.name ?? null,
    input_source: source,
    mix_inputs: selectedMode === 'mix',
    standby_input_device_index: standby?.index ?? null,
    standby_input_device_name: standby?.name ?? null,
    keep_other_input_open: Boolean(standby),
  }
}

export function recordingModeName(mode, sameDevice = false) {
  if (mode === 'microphone') return '麦克风单录'
  if (mode === 'usb') return '声卡单录'
  return sameDevice ? '单路（两项选择了同一设备）' : '双路混音'
}
