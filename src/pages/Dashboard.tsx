import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useToast } from '../components/toastContext'
import { useAuth } from '../components/authContext'
import { getJson } from '../lib/api'
import { money } from '../lib/format'
import {
  collectionBreakdown,
  demoAlerts,
  recentTransactions,
  salesTrend,
  shiftStatus,
} from '../data/sampleData'

interface ApiTransaction {
  id: string
  created_at: string
  tender: string
  volume_litres: string
  amount: string
}

interface DailySales {
  grand_total_amount: string
  grand_total_litres: string
  totals: Array<{ product: string; volume_litres: string; amount: string }>
}

interface Collections {
  slices: Array<{ mode: string; amount: string }>
  total: string
}

interface TxnRow {
  time: string
  label: string
  mode: string
  amount: string
  status: string
  tone: 'green' | 'amber' | 'blue' | 'red'
}

interface LiveState {
  owner: string | null
  transactions: TxnRow[] | null
  salesTotal: number | null
  litresTotal: number | null
  litresSplit: string | null
  cashCollected: number | null
  collections: Array<{ mode: string; amount: string; share: string }> | null
}

const EMPTY_LIVE: LiveState = {
  owner: null,
  transactions: null,
  salesTotal: null,
  litresTotal: null,
  litresSplit: null,
  cashCollected: null,
  collections: null,
}

function greeting(): string {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

export default function Dashboard() {
  const toast = useToast()
  const navigate = useNavigate()
  const { session } = useAuth()
  const [live, setLive] = useState<LiveState>(EMPTY_LIVE)
  const [txnQuery, setTxnQuery] = useState('')

  useEffect(() => {
    if (!session) return
    let cancelled = false
    ;(async () => {
      const today = new Date().toISOString().slice(0, 10)
      try {
        const [sales, daily, collections] = await Promise.all([
          getJson<ApiTransaction[]>('/api/v1/sales?limit=4'),
          getJson<DailySales>(`/api/v1/reports/daily-sales?date=${today}`),
          getJson<Collections>(`/api/v1/reports/collections?date=${today}`),
        ])
        if (cancelled) return
        const totalCollection = Number(collections.total) || 0
        const petrol = daily.totals.find((t) => t.product.toLowerCase().includes('petrol'))
        const diesel = daily.totals.find((t) => t.product.toLowerCase().includes('diesel'))
        setLive({
          owner: session.employee.code,
          transactions: sales.map((s) => ({
            time: new Date(s.created_at).toLocaleTimeString('en-IN', {
              hour: '2-digit',
              minute: '2-digit',
            }),
            label: `Fuel sale · ${Number(s.volume_litres).toLocaleString('en-IN')} L`,
            mode: s.tender.toUpperCase(),
            amount: money(Number(s.amount)),
            status: 'Recorded',
            tone: 'green',
          })),
          salesTotal: Number(daily.grand_total_amount) || 0,
          litresTotal: Number(daily.grand_total_litres) || 0,
          litresSplit:
            petrol && diesel
              ? `Petrol ${Number(petrol.volume_litres).toLocaleString('en-IN')} L · Diesel ${Number(diesel.volume_litres).toLocaleString('en-IN')} L`
              : null,
          cashCollected:
            Number(
              collections.slices.find((s) => s.mode.toLowerCase() === 'cash')?.amount ?? null,
            ) || null,
          collections: collections.slices.map((s) => ({
            mode: s.mode.charAt(0).toUpperCase() + s.mode.slice(1),
            amount: money(Number(s.amount)),
            share:
              totalCollection > 0
                ? `${((Number(s.amount) / totalCollection) * 100).toFixed(1)}%`
                : '0.0%',
          })),
        })
      } catch {
        /* API unreachable — isLive derivation keeps demo data */
      }
    })()
    return () => {
      cancelled = true
    }
  }, [session])

  const isLive = Boolean(
    session && live.owner === session.employee.code && live.transactions !== null,
  )
  const txnList: TxnRow[] =
    isLive && live.transactions ? live.transactions : [...recentTransactions]
  const mixList = isLive && live.collections ? live.collections : [...collectionBreakdown]

  const q = txnQuery.trim().toLowerCase()
  const visibleTransactions = txnList.filter((txn) =>
    q === ''
      ? true
      : `${txn.time} ${txn.label} ${txn.mode} ${txn.amount} ${txn.status}`
          .toLowerCase()
          .includes(q),
  )

  const salesValue = isLive && live.salesTotal !== null ? money(live.salesTotal) : '₹ 2,84,650'
  const litresValue =
    isLive && live.litresTotal !== null ? live.litresTotal.toLocaleString('en-IN') : '3,842.6'
  const litresDetail = isLive
    ? (live.litresSplit ?? 'From closed shifts')
    : 'Petrol 1,624 L · Diesel 2,219 L'
  const cashValue = isLive
    ? live.cashCollected !== null
      ? money(live.cashCollected)
      : '—'
    : '₹ 96,420'
  const cashShare = isLive
    ? live.cashCollected !== null && live.salesTotal
      ? `${((live.cashCollected / live.salesTotal) * 100).toFixed(1)}% of sales`
      : 'No cash collections recorded today'
    : '33.9% of sales'

  return (
    <>
      <div className="heading">
        <div>
          <h1>
            {greeting()}, {session?.employee.name.split(' ')[0] ?? 'Deep'}
          </h1>
          <div className="sub">
            {session
              ? `Station ${session.station.code} · signed in as ${session.employee.code} (${session.employee.role})`
              : "Here's what's happening at your station today."}
          </div>
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
        ⓘ <b>{isLive ? 'Live:' : session ? 'Offline:' : 'Demo data:'}</b>{' '}
        {isLive
          ? 'Figures below come from the OpenBunk API (closed shifts and recorded sales only).'
          : session
            ? 'Signed in but backend not reachable (or no data yet) — showing illustrative sample data.'
            : 'All figures below are illustrative. This prototype does not connect to a dispenser, payment gateway, or live database.'}
      </div>

      <div className="grid stats">
        <div className="card">
          <div className="stat-top">
            Today's sales <span className="stat-icon">₹</span>
          </div>
          <div className="value">{salesValue}</div>
          <div className="delta">
            {isLive ? (
              <span className="live-tag">● Live</span>
            ) : (
              <>
                ↑ 8.4% <span className="muted">vs yesterday</span>
              </>
            )}
          </div>
        </div>
        <div className="card">
          <div className="stat-top">
            Fuel dispensed <span className="stat-icon">⛽</span>
          </div>
          <div className="value">
            {litresValue} <small className="unit">L</small>
          </div>
          <div className="delta">{litresDetail}</div>
        </div>
        <div className="card">
          <div className="stat-top">
            Cash collected <span className="stat-icon">₹</span>
          </div>
          <div className="value">{cashValue}</div>
          <div className="delta">{cashShare}</div>
        </div>
        <div className="card">
          <div className="stat-top">
            Credit outstanding <span className="stat-icon">↗</span>
          </div>
          <div className="value">{isLive ? '—' : '₹ 1,42,800'}</div>
          <div className="delta warn">
            {isLive ? 'No API endpoint yet' : '12 customers · Due follow-up'}
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="cardhead">
          <h3>Collection mix today</h3>
          <span className="small">{isLive ? 'Live · API' : 'Demo data'}</span>
        </div>
        <div className="kpirow">
          {mixList.map((row) => (
            <div className="kpi" key={row.mode}>
              <span>{row.mode}</span>
              <b>{row.amount}</b>
              <span className="small">{row.share} of collections</span>
            </div>
          ))}
        </div>
      </div>

      <div className="card alerts" style={{ marginTop: 16 }}>
        <div className="cardhead">
          <h3>Alerts</h3>
          <span className="small">Demo data · {demoAlerts.length} open</span>
        </div>
        <ul className="alertlist">
          {demoAlerts.map((alert) => (
            <li key={alert.text}>
              <span className={`pill ${alert.tone}`}>!</span>
              <span>{alert.text}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="grid two" style={{ marginTop: 16 }}>
        <div className="card">
          <div className="cardhead">
            <h3>Sales trend</h3>
            <span className="small">Sample chart · no API history yet</span>
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
          <div className="actions">
            <input
              className="search"
              placeholder="Filter transactions…"
              value={txnQuery}
              onChange={(event) => setTxnQuery(event.target.value)}
              aria-label="Filter transactions"
            />
            <Link to="/reports" className="btn">
              View all →
            </Link>
          </div>
        </div>
        <div className="tablewrap">
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
              {visibleTransactions.map((txn) => (
                <tr key={`${txn.time}-${txn.label}-${txn.amount}`}>
                  <td>{txn.time}</td>
                  <td>{txn.label}</td>
                  <td>{txn.mode}</td>
                  <td className="right">{txn.amount}</td>
                  <td>
                    <span className={`pill ${txn.tone}`}>{txn.status}</span>
                  </td>
                </tr>
              ))}
              {visibleTransactions.length === 0 && (
                <tr>
                  <td colSpan={5} className="emptyhint">
                    {isLive
                      ? 'No transactions recorded yet — close a shift or record a sale.'
                      : `No transactions match “${txnQuery}”.`}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {session && !isLive && (
          <p className="small" style={{ marginTop: 10 }}>
            Sample data — backend unreachable or nothing recorded yet.
          </p>
        )}
        {!session && (
          <p className="small" style={{ marginTop: 10 }}>
            Sample transactions — sign in to see live sales.
          </p>
        )}
      </div>
    </>
  )
}
