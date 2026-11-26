import { createContext, useContext, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { api, clearSession, getToken, loadUser, saveSession } from './api'

const AuthCtx = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => (getToken() ? loadUser() : null))

  async function login(email, password, portal, remember = true) {
    const res = await api('/auth/login', { method: 'POST', body: { email, password, portal } })
    saveSession(res.token, res.user, remember)
    setUser(res.user)
    return res.user
  }
  async function register(body) {
    const res = await api('/auth/register', { method: 'POST', body })
    saveSession(res.token, res.user, true)
    setUser(res.user)
    return res.user
  }
  function logout() {
    clearSession()
    setUser(null)
  }
  function update(u) {
    const next = { ...user, ...u }
    saveSession(getToken(), next)
    setUser(next)
  }
  return <AuthCtx.Provider value={{ user, login, register, logout, update }}>{children}</AuthCtx.Provider>
}

export const useAuth = () => useContext(AuthCtx)

/** Client-side guard for navigation only; the API enforces roles server-side. */
export function RequireRole({ role, children }) {
  const { user } = useAuth()
  const loc = useLocation()
  if (!user) return <Navigate to={role === 'admin' ? '/admin/login' : '/login'} state={{ from: loc.pathname }} replace />
  if (user.role !== role) return <Navigate to={user.role === 'admin' ? '/admin' : '/student'} replace />
  return children
}
