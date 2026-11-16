import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../components/authContext'
import { LogoMark } from '../components/icons'
import { ApiHttpError, ApiOfflineError } from '../lib/api'
import { STATION } from '../config/station'

export default function Login() {
  const { login, online } = useAuth()
  const navigate = useNavigate()
  const [stationCode, setStationCode] = useState<string>(STATION.code)
  const [employeeCode, setEmployeeCode] = useState('EMP-00')
  const [pin, setPin] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(stationCode.trim(), employeeCode.trim(), pin)
      navigate('/', { replace: true })
    } catch (err) {
      if (err instanceof ApiOfflineError) {
        setError('Backend is not reachable. Sign-in requires a reachable server.')
      } else if (err instanceof ApiHttpError) {
        setError(err.status === 429 ? err.message : 'Invalid station code, employee code or PIN.')
      } else {
        setError('Sign-in failed. Please try again.')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-wrap">
      <div className="login-brand">
        <div className="brand">
          <LogoMark size={42} />
          <div>
            <b>DeepBNK</b>
            <small>Station operations</small>
          </div>
        </div>
        <div>
          <h2>
            Your station,
            <br />
            one screen.
          </h2>
          <p>
            Shift readings, fuel stock, credit ledgers and reports — built for the counter, works on
            any phone.
          </p>
          <div className="feature">
            <span className="stat-icon">◷</span>
            <span>Close shifts and record meter readings from the forecourt</span>
          </div>
          <div className="feature">
            <span className="stat-icon">⛽</span>
            <span>Track fuel stock and credit sales without spreadsheets</span>
          </div>
        </div>
        <p className="small" style={{ color: '#6f83a1' }}>
          Installable PWA · works offline
        </p>
      </div>
      <div className="login-side">
        <form className="card login-card" onSubmit={onSubmit}>
          <div className="brand" style={{ padding: 0, marginBottom: 18 }}>
            <LogoMark size={38} />
            <div>
              <b style={{ color: 'inherit' }}>DeepBNK</b>
              <small style={{ color: 'var(--ink-soft)' }}>Sign in to the station API</small>
            </div>
          </div>

          <div className="field">
            <label htmlFor="station-code">Station code</label>
            <input
              id="station-code"
              value={stationCode}
              onChange={(e) => setStationCode(e.target.value)}
              autoComplete="off"
              required
            />
          </div>
          <div className="field" style={{ marginTop: 12 }}>
            <label htmlFor="employee-code">Employee code</label>
            <input
              id="employee-code"
              value={employeeCode}
              onChange={(e) => setEmployeeCode(e.target.value)}
              autoComplete="username"
              required
            />
          </div>
          <div className="field" style={{ marginTop: 12 }}>
            <label htmlFor="pin">PIN</label>
            <input
              id="pin"
              type="password"
              inputMode="numeric"
              value={pin}
              onChange={(e) => setPin(e.target.value)}
              autoComplete="current-password"
              minLength={6}
              required
            />
          </div>

          {error && (
            <div className="field-error" role="alert" style={{ marginTop: 12 }}>
              {error}
            </div>
          )}
          {!online && (
            <div className="notice" style={{ marginTop: 12, marginBottom: 0 }}>
              ⓘ Backend not reachable — sign-in is unavailable until the server is online.
            </div>
          )}

          <div className="formactions" style={{ marginTop: 18 }}>
            <button
              type="submit"
              className="btn primary"
              disabled={busy}
              style={{ width: '100%', justifyContent: 'center' }}
            >
              {busy ? 'Signing in…' : 'Sign in'}
            </button>
          </div>
          <p className="small" style={{ marginTop: 12, textAlign: 'center' }}>
            PINs are at least 6 digits. Ask the station owner for your employee code and PIN.
          </p>
        </form>
      </div>
    </div>
  )
}
