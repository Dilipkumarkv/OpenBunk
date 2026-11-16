/**
 * OpenBunk API client (Phase 06).
 *
 * - Base URL from VITE_API_URL (default http://localhost:8000)
 * - Tokens in sessionStorage (tab-scoped, never in localStorage/repo)
 * - Access token auto-refreshed single-flight on expiry; one retry after 401
 * - Every request has a 5s timeout; network failure throws ApiOfflineError
 *   so callers can fall back to clearly-labeled demo data.
 */

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'
const TOKEN_KEY = 'openbunk.tokens.v1'
const HEALTH_KEY = 'openbunk.online.v1'

export class ApiOfflineError extends Error {
  constructor(message = 'OpenBunk backend is not reachable') {
    super(message)
    this.name = 'ApiOfflineError'
  }
}
export class ApiAuthError extends Error {
  constructor(message = 'Session expired — please sign in again') {
    super(message)
    this.name = 'ApiAuthError'
  }
}
export class ApiHttpError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiHttpError'
    this.status = status
  }
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  access_expires_at: string
  refresh_expires_at: string
}

export interface SessionInfo {
  employee: { code: string; name: string; role: string }
  station: { code: string; name: string }
}

export function loadTokens(): TokenPair | null {
  try {
    const raw = sessionStorage.getItem(TOKEN_KEY)
    return raw ? (JSON.parse(raw) as TokenPair) : null
  } catch {
    return null
  }
}
export function saveTokens(tokens: TokenPair): void {
  sessionStorage.setItem(TOKEN_KEY, JSON.stringify(tokens))
  sessionStorage.setItem(HEALTH_KEY, '1')
}
export function clearTokens(): void {
  sessionStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(HEALTH_KEY)
}

function isExpired(iso: string | undefined): boolean {
  if (!iso) return true
  return Date.now() > Date.parse(iso) - 30_000 // refresh slightly early
}

async function rawFetch(path: string, init: RequestInit, token?: string): Promise<Response> {
  const headers: Record<string, string> = {
    ...((init.headers as Record<string, string>) ?? {}),
  }
  // FormData must keep the browser-set multipart boundary — never force a JSON content type
  if (!(init.body instanceof FormData)) {
    headers['Content-Type'] = headers['Content-Type'] ?? 'application/json'
  }
  if (token) headers['Authorization'] = `Bearer ${token}`
  try {
    return await fetch(`${BASE}${path}`, {
      ...init,
      headers,
      signal: AbortSignal.timeout(5000),
    })
  } catch {
    throw new ApiOfflineError()
  }
}

let refreshing: Promise<TokenPair | null> | null = null

async function refreshTokens(): Promise<TokenPair | null> {
  const tokens = loadTokens()
  if (!tokens || isExpired(tokens.refresh_expires_at)) return null
  if (refreshing) return refreshing
  refreshing = (async () => {
    try {
      const res = await fetch(`${BASE}/api/v1/session/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: tokens.refresh_token }),
        signal: AbortSignal.timeout(5000),
      })
      if (!res.ok) return null
      const pair = (await res.json()) as TokenPair
      saveTokens(pair)
      return pair
    } catch {
      return null
    } finally {
      // allow future refresh attempts once this one settles
      setTimeout(() => {
        refreshing = null
      }, 0)
    }
  })()
  return refreshing
}

async function ensureAccessToken(): Promise<string | null> {
  const tokens = loadTokens()
  if (!tokens) return null
  if (!isExpired(tokens.access_expires_at)) return tokens.access_token
  const pair = await refreshTokens()
  return pair?.access_token ?? null
}

export async function request(path: string, init: RequestInit = {}): Promise<Response> {
  let token = await ensureAccessToken()
  let res = await rawFetch(path, init, token ?? undefined)
  if (res.status === 401 && token) {
    clearTokens()
    token = await ensureAccessToken() // forced refresh attempt
    if (token) {
      res = await rawFetch(path, init, token)
    } else {
      throw new ApiAuthError()
    }
  }
  return res
}

export async function getJson<T>(path: string): Promise<T> {
  const res = await request(path)
  if (!res.ok) throw new ApiHttpError(res.status, `GET ${path} failed with ${res.status}`)
  return (await res.json()) as T
}

export async function putJson<T>(path: string, body: unknown): Promise<T> {
  const res = await request(path, { method: 'PUT', body: JSON.stringify(body) })
  if (!res.ok) {
    const detail = await res.text()
    throw new ApiHttpError(
      res.status,
      detail.slice(0, 300) || `PUT ${path} failed with ${res.status}`,
    )
  }
  return (await res.json()) as T
}

export async function postJson<T>(
  path: string,
  body: unknown,
  extraHeaders?: Record<string, string>,
): Promise<T> {
  const res = await request(path, {
    method: 'POST',
    body: JSON.stringify(body),
    headers: { ...extraHeaders },
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new ApiHttpError(
      res.status,
      detail.slice(0, 300) || `POST ${path} failed with ${res.status}`,
    )
  }
  return (await res.json()) as T
}

export async function login(
  stationCode: string,
  employeeCode: string,
  pin: string,
): Promise<SessionInfo> {
  const res = await fetch(`${BASE}/api/v1/session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ station_code: stationCode, employee_code: employeeCode, pin }),
    signal: AbortSignal.timeout(5000),
  }).catch(() => {
    throw new ApiOfflineError()
  })
  if (!res.ok) {
    if (res.status === 429)
      throw new ApiHttpError(429, 'Too many failed attempts — account locked, try later')
    throw new ApiHttpError(res.status, 'Invalid station code, employee code or PIN')
  }
  const body = (await res.json()) as TokenPair & SessionInfo
  saveTokens(body)
  return { employee: body.employee, station: body.station }
}

export async function logout(): Promise<void> {
  const tokens = loadTokens()
  try {
    if (tokens) {
      await rawFetch(
        '/api/v1/session',
        { method: 'DELETE', body: JSON.stringify({ refresh_token: tokens.refresh_token }) },
        tokens.access_token,
      )
    }
  } catch {
    /* best effort */
  } finally {
    clearTokens()
  }
}

export async function healthCheck(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/health`, { signal: AbortSignal.timeout(3000) })
    return res.ok
  } catch {
    return false
  }
}
