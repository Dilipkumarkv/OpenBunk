import { useCallback, useEffect, useState, type ReactNode } from 'react'
import {
  ApiOfflineError,
  clearTokens,
  getJson,
  healthCheck,
  loadTokens,
  login as apiLogin,
  logout as apiLogout,
  type SessionInfo,
} from '../lib/api'
import { authContext } from './authContext'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<'loading' | 'ready'>('loading')
  const [online, setOnline] = useState(false)
  const [session, setSession] = useState<SessionInfo | null>(null)

  const recheckConnection = useCallback(async () => {
    const up = await healthCheck()
    setOnline(up)
    return up
  }, [])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const up = await healthCheck()
      if (cancelled) return
      setOnline(up)
      if (up && loadTokens()) {
        try {
          const me = await getJson<SessionInfo>('/api/v1/me')
          if (!cancelled) setSession(me)
        } catch (error) {
          if (error instanceof ApiOfflineError) setOnline(false)
          else clearTokens()
        }
      }
      if (!cancelled) setStatus('ready')
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (stationCode: string, employeeCode: string, pin: string) => {
    const me = await apiLogin(stationCode, employeeCode, pin)
    setSession(me)
    setOnline(true)
  }, [])

  const logout = useCallback(async () => {
    await apiLogout()
    setSession(null)
  }, [])

  return (
    <authContext.Provider value={{ status, online, session, login, logout, recheckConnection }}>
      {children}
    </authContext.Provider>
  )
}
