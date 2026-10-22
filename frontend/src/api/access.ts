// The visitor key is a bearer capability, not a login identity. Never log it.
let visitorKey = ''
let adminKey = ''

export function visitorHeaders(): Record<string, string> {
  if (!visitorKey) {
    try { visitorKey = localStorage.getItem('guide.visitor-key') || '' } catch { /* memory-only in restricted browsers */ }
    if (!/^[a-f0-9]{32,128}$/.test(visitorKey)) visitorKey = crypto.randomUUID().replace(/-/g, '')
    try { localStorage.setItem('guide.visitor-key', visitorKey) } catch { /* capability lasts this page only */ }
  }
  return { 'X-Visitor-Key': visitorKey }
}

export function setAdminKey(value: string) { adminKey = value.trim() }
export function accessHeaders(url: string, method = 'GET'): Record<string, string> {
  const headers = visitorHeaders()
  const admin = url.startsWith('/api/admin/') || url.startsWith('/api/behavior') || url.startsWith('/api/dashboard')
    || (url.startsWith('/api/feedback') && method.toUpperCase() === 'GET')
  if (admin && adminKey) headers['X-Admin-Key'] = adminKey
  return headers
}
