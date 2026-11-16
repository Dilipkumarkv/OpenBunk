import { useToast } from '../components/toastContext'

export default function Settings() {
  const toast = useToast()

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
          <h3>Station profile</h3>
          <span className="pill blue">Single station</span>
        </div>
        <div className="formgrid">
          <div className="field">
            <label htmlFor="station-name">Station name</label>
            <input id="station-name" defaultValue="OpenBunk Demo Station" />
          </div>
          <div className="field">
            <label htmlFor="station-code">Station code</label>
            <input id="station-code" defaultValue="OB-001" />
          </div>
          <div className="field">
            <label htmlFor="address">Address</label>
            <input id="address" defaultValue="Melkote, Karnataka" />
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
            onClick={() => toast('Demo only: settings are not persisted.')}
          >
            Save settings
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
            <b>0.1 · UI Prototype</b>
          </div>
          <div className="kpi">
            <span>Environment</span>
            <b>Demo / Sample data</b>
          </div>
          <div className="kpi">
            <span>Persistence</span>
            <b>Not connected</b>
          </div>
        </div>
        <p className="small" style={{ marginTop: 14 }}>
          Production requirements: authentication, role-based access, database migrations, audit
          trail, encrypted backups, and secure deployment.
        </p>
      </div>
    </>
  )
}
