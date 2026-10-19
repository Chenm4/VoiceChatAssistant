export function preferredRecordingDevice(devices, saved, source) {
  const match = saved && (devices.find(device => device.index === saved.index && device.name === saved.name)
    || devices.find(device => device.name === saved.name))
  if (match) return match
  if (source === 'usb') {
    const soundCard = devices.find(device => /usb/i.test(device.name) && !/camera|webcam|microphone|麦克风|摄像/i.test(device.name))
    if (soundCard) return soundCard
  }
  return devices.find(device => /macbook|built.in|内置/i.test(device.name) && !/usb/i.test(device.name)) || null
}
