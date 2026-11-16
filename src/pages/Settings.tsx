import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useToast } from '../components/toastContext'
import { useAuth } from '../components/authContext'
import { request } from '../lib/api'
import { STATION } from '../config/station'

export default function Settings() {
  const toast = useToast()
  const { session, online, logout, recheckConnection } = useAuth()
  const [exportPin, setExportPin] = useState('')
  const [exporting, setExporting] = useState(false)

  const downloadExport = async () => {
    if (!session) {
      toast('Sign in as owner to export station data.')
      return
    }
    setExporting(true)
    try {
      const response = await request('/api/v1/export', {
        headers: { 'X-Reauth-Pin': exportPin },
      })
      if (response.status === 403) {
        toast('Export requires the owner role.')
        return
      }
      if (response.status === 401) {
        toast('PIN rejected — export aborted.')
        return
      }
      if (!response.ok) {
        toast(`Export failed (${response.status}).`)
        return
      }
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'deepbnk-export.json'
      a.click()
      URL.revokeObjectURL(url)
      toast('Station export downloaded (deepbnk-export.json).')
    } catch {
      toast('Backend not reachable — export not possible.')
    } finally {
      setExporting(false)
    }
  }

  return (
    <>
      <div className="heading">
        <div>
          <h1>Station settings</h1>
          <div className="sub">Configure this single station.</div>
        </div>
      </div>

      <div className="card">
        <div className="cardhead">
          <h3>Connection</h3>
          <span className={session ? 'pill green' : online ? 'pill blue' : 'pill amber'}>
            {session ? 'Connected' : online ? 'API online' : 'Offline'}
          </span>
        </div>
        <div className="kpirow">
          <div className="kpi">
            <span>Backend</span>
            <b>{online ? 'Reachable' : 'Not reachable'}</b>
          </div>
          <div className="kpi">
            <span>Signed in</span>
            <b>
              {session
                ? `${session.employee.name} (${session.employee.role})`
                : 'No — not signed in'}
            </b>
          </div>
          <div className="kpi">
            <span>Station</span>
            <b>
              {session
                ? `${session.station.code} · ${session.station.name}`
                : `${STATION.code} · ${STATION.name}`}
            </b>
          </div>
        </div>
        <div className="formactions" style={{ marginTop: 14 }}>
          <button className="btn" onClick={() => void recheckConnection()}>
            Re-check connection
          </button>
          {session ? (
            <button className="btn" onClick={() => void logout()}>
              Sign out
            </button>
          ) : (
            <Link to="/login" className="btn primary">
              Sign in
            </Link>
          )}
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="cardhead">
          <h3>Station profile</h3>
          <span className="pill blue">Single station</span>
        </div>
        <div className="formgrid">
          <div className="field">
            <label htmlFor="station-name">Station name</label>
            <input id="station-name" defaultValue={session?.station.name ?? STATION.name} />
          </div>
          <div className="field">
            <label htmlFor="station-code">Station code</label>
            <input id="station-code" defaultValue={session?.station.code ?? STATION.code} />
          </div>
          <div className="field">
            <label htmlFor="address">Address</label>
            <input id="address" defaultValue={STATION.address} />
          </div>
          <div className="field">
            <label htmlFor="timezone">Timezone</label>
            <select id="timezone" defaultValue="ist">
              <option value="ist">Asia/Kolkata (IST)</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="currency">Currency</label>
            <select id="currency" defaultValue="inr">
              <option value="inr">INR — Indian Rupee</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="business-day">Business day starts</label>
            <select id="business-day" defaultValue="0600">
              <option value="0600">06:00 AM</option>
              <option value="0000">12:00 AM</option>
            </select>
          </div>
        </div>
        <div className="formactions">
          <button
            className="btn primary"
            onClick={() => toast('Station profile editing is not available yet.')}
          >
            Save settings
          </button>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="cardhead">
          <h3>Data & backup</h3>
          <span className="small">Owner-only action</span>
        </div>
        <p className="small">
          Download a complete JSON export of this station (no credentials included). Requires the
          owner role and your PIN to re-authenticate.
        </p>
        <div className="formactions" style={{ alignItems: 'center' }}>
          <input
            aria-label="PIN to confirm export"
            type="password"
            placeholder="PIN"
            value={exportPin}
            onChange={(event) => setExportPin(event.target.value)}
            style={{ maxWidth: 140, border: '1px solid #dce4ef', borderRadius: 8, padding: 10 }}
          />
          <button
            className="btn"
            onClick={() => void downloadExport()}
            disabled={exporting || exportPin.length < 4}
          >
            {exporting ? 'Exporting…' : '⇩ Download station export'}
          </button>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="cardhead">
          <h3>System & data</h3>
        </div>
        <div className="kpirow">
          <div className="kpi">
            <span>Version</span>
            <b>0.7 · Station operations</b>
          </div>
          <div className="kpi">
            <span>Environment</span>
            <b>{online ? 'Backend reachable' : 'Offline'}</b>
          </div>
          <div className="kpi">
            <span>Persistence</span>
            <b>{session ? 'Connected' : 'Not connected'}</b>
          </div>
        </div>
        <p className="small" style={{ marginTop: 14 }}>
          Production requirements: account recovery, restore drill, external PostgreSQL backup,
          HTTPS, monitoring. See docs/security-checklist.md — not yet cleared for real data.
        </p>
      </div>
    </>
  )
}
