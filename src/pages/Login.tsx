import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../components/authContext'
import { ApiHttpError, ApiOfflineError } from '../lib/api'

export default function Login() {
  const { login, online } = useAuth()
  const navigate = useNavigate()
  const [stationCode, setStationCode] = useState('OB-001')
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
        setError('Backend is not reachable. Demo mode is available, but nothing is saved.')
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
      <form className="card login-card" onSubmit={onSubmit}>
        <div className="brand" style={{ padding: 0, marginBottom: 18 }}>
          <div className="logo">O</div>
          <div>
            <b style={{ color: 'inherit' }}>OpenBunk</b>
            <small style={{ color: 'var(--muted)' }}>Sign in to the station API</small>
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
            ⓘ Backend not reachable — the app will run in clearly-labeled demo mode.
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
        <button
          type="button"
          className="btn"
          style={{ marginTop: 10, width: '100%', justifyContent: 'center' }}
          onClick={() => navigate('/')}
        >
          Continue in demo mode →
        </button>
        <p className="small" style={{ marginTop: 12, textAlign: 'center' }}>
          PINs are at least 6 digits. Demo accounts are EMP-00…EMP-04 in development only; ask the
          station owner for your PIN. Production deploys do not seed demo employees.
        </p>
      </form>
    </div>
  )
}
