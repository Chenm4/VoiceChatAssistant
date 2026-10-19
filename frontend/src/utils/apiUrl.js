export function apiUrl(value, baseUrl = import.meta.env?.BASE_URL || '/') {
  if (value === '/api' || value.startsWith('/api/') || value.startsWith('/api?')) {
    return baseUrl.replace(/\/$/, '') + value
  }
  return value
}
