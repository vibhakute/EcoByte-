import { useCallback, useEffect, useRef, useState } from 'react'

const TOKEN_KEY = 'ecobyte_token'
const USER_KEY = 'ecobyte_user'

// "Remember me" keeps the session in localStorage; otherwise sessionStorage (ends with the tab).
const store = () => {
  try { return sessionStorage.getItem(TOKEN_KEY) ? sessionStorage : localStorage } catch { return null }
}
export function getToken() {
  try { return store()?.getItem(TOKEN_KEY) || null } catch { return null }
}
export function saveSession(token, user, remember) {
  try {
    const keep = remember ?? (localStorage.getItem(TOKEN_KEY) !== null || !sessionStorage.getItem(TOKEN_KEY))
    const s = keep ? localStorage : sessionStorage
    clearSession()
    s.setItem(TOKEN_KEY, token)
    s.setItem(USER_KEY, JSON.stringify(user))
  } catch { /* storage unavailable: session lasts for this page only */ }
}
export function loadUser() {
  try { return JSON.parse(store()?.getItem(USER_KEY) || 'null') } catch { return null }
}
export function clearSession() {
  try {
    for (const s of [localStorage, sessionStorage]) { s.removeItem(TOKEN_KEY); s.removeItem(USER_KEY) }
  } catch { /* ignore */ }
}

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status }
}

function formatDetail(detail) {
  if (!detail) return 'Something went wrong'
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map(d => {
      const field = (d.loc || []).filter(x => x !== 'body').join(' › ')
      return field ? `${field}: ${d.msg}` : d.msg
    }).join('; ')
  }
  return JSON.stringify(detail)
}

export async function api(path, { method = 'GET', body, params, raw } = {}) {
  const url = new URL('/api' + path, window.location.origin)
  if (params) Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v)
  })
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  let payload
  if (body instanceof FormData) payload = body
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body) }
  const res = await fetch(url, { method, headers, body: payload })
  if (res.status === 401 && !path.startsWith('/auth/login')) {
    clearSession()
    const admin = window.location.pathname.startsWith('/admin')
    window.location.assign(admin ? '/admin/login?expired=1' : '/login?expired=1')
    throw new ApiError(401, 'Session expired')
  }
  if (!res.ok) {
    let msg = res.statusText
    try { msg = formatDetail((await res.json()).detail) } catch { /* non-JSON error */ }
    throw new ApiError(res.status, msg)
  }
  if (raw) return res
  return res.json()
}

/** Fetch on mount and whenever deps change. Returns {data, error, loading, reload, setData}. */
export function useApi(path, params, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true })
  const seq = useRef(0)
  const key = JSON.stringify(params || {})
  const load = useCallback(async (quiet = false) => {
    const id = ++seq.current
    if (!quiet) setState(s => ({ ...s, loading: true, error: null }))
    try {
      const data = await api(path, { params })
      if (id === seq.current) setState({ data, error: null, loading: false })
    } catch (e) {
      if (id === seq.current) setState(s => ({ ...s, error: e.message, loading: false }))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, key, ...deps])
  useEffect(() => { if (path) load() }, [load, path])
  return { ...state, reload: load, setData: d => setState(s => ({ ...s, data: typeof d === 'function' ? d(s.data) : d })) }
}

export async function download(path, params, filename) {
  const res = await api(path, { params, raw: true })
  const blob = await res.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(a.href), 2000)
}
