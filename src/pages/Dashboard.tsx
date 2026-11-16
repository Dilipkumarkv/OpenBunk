import { Link, useNavigate } from 'react-router-dom'
import { useToast } from '../components/toastContext'
import { recentTransactions, salesTrend, shiftStatus } from '../data/sampleData'

function greeting(): string {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

export default function Dashboard() {
  const toast = useToast()
  const navigate = useNavigate()

  return (
    <>
      <div className="heading">
        <div>
          <h1>{greeting()}, Deep</h1>
          <div className="sub">Here's what's happening at your station today.</div>
        </div>
        <div className="actions">
          <button className="btn" onClick={() => toast('Demo data exported (prototype action).')}>
            ⇩ Export
          </button>
          <button className="btn primary" onClick={() => navigate('/shifts')}>
            ＋ Close a shift
          </button>
        </div>
      </div>

      <div className="notice">
        ⓘ <b>Demo data:</b> All figures below are illustrative. This prototype does not connect to a
        dispenser, payment gateway, or live database.
      </div>

      <div className="grid stats">
        <div className="card">
          <div className="stat-top">
            Today's sales <span className="stat-icon">₹</span>
          </div>
          <div className="value">₹ 2,84,650</div>
          <div className="delta">
            ↑ 8.4% <span className="muted">vs yesterday</span>
          </div>
        </div>
        <div className="card">
          <div className="stat-top">
            Fuel dispensed <span className="stat-icon">⛽</span>
          </div>
          <div className="value">
            3,842.6 <small className="unit">L</small>
          </div>
          <div className="delta">Petrol 1,624 L · Diesel 2,219 L</div>
        </div>
        <div className="card">
          <div className="stat-top">
            Cash collected <span className="stat-icon">₹</span>
          </div>
          <div className="value">₹ 96,420</div>
          <div className="delta">33.9% of sales</div>
        </div>
        <div className="card">
          <div className="stat-top">
            Credit outstanding <span className="stat-icon">↗</span>
          </div>
          <div className="value">₹ 1,42,800</div>
          <div className="delta warn">12 customers · Due follow-up</div>
        </div>
      </div>

      <div className="grid two">
        <div className="card">
          <div className="cardhead">
            <h3>Sales trend</h3>
            <span className="small">Last 7 days · ₹</span>
          </div>
          <div className="barwrap">
            {salesTrend.map((bar) => (
              <div className="barcol" key={bar.day}>
                <div
                  className={'today' in bar && bar.today ? 'bar today' : 'bar'}
                  style={{ height: `${bar.height}%` }}
                />
                <span className="barlabel">{bar.day}</span>
              </div>
            ))}
          </div>
          <div className="legend">
            <span>
              <i className="dot" />
              Daily sales
            </span>
            <span>Today highlighted</span>
          </div>
        </div>

        <div className="card">
          <div className="cardhead">
            <h3>Shift status</h3>
            <span className="pill green">2 completed</span>
          </div>
          {shiftStatus.map((shift) => (
            <div className="shift-row" key={shift.name}>
              <div>
                <b>{shift.name}</b>
                <div className="small">{shift.meta}</div>
              </div>
              <span className={`pill ${shift.tone}`}>{shift.status}</span>
            </div>
          ))}
          <Link to="/shifts" className="btn block">
            View shift register →
          </Link>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="cardhead">
          <h3>Recent transactions</h3>
          <Link to="/reports" className="btn">
            View all →
          </Link>
        </div>
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Transaction</th>
              <th>Mode</th>
              <th className="right">Amount</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {recentTransactions.map((txn) => (
              <tr key={`${txn.time}-${txn.label}`}>
                <td>{txn.time}</td>
                <td>{txn.label}</td>
                <td>{txn.mode}</td>
                <td className="right">{txn.amount}</td>
                <td>
                  <span className={`pill ${txn.tone}`}>{txn.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
