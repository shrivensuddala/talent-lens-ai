const base = import.meta.env.VITE_API_URL || '/api'
export async function api(path, options = {}) {
  const headers = {...options.headers}
  const token = localStorage.getItem('talentlens_token')
  if (token) headers.Authorization = `Bearer ${token}`
  const response = await fetch(base + path, {...options, headers})
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body.detail || 'Request failed')
  return body
}
