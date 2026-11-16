import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../components/authContext'
import { getJson } from '../lib/api'
import { money } from '../lib/format'
import { STATION } from '../config/station'

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
        /* API unreachable — the page shows empty states until data loads */
      }
    })()
    return () => {
      cancelled = true
    }
  }, [session])

  const isLive = Boolean(
    session && live.owner === session.employee.code && live.transactions !== null,
  )
  const station = session
    ? { name: session.station.name, code: session.station.code }
    : { name: STATION.name, code: STATION.code }
  const txnList: TxnRow[] = isLive && live.transactions ? live.transactions : []
  const mixList = isLive && live.collections ? live.collections : []

  const q = txnQuery.trim().toLowerCase()
  const visibleTransactions = txnList.filter((txn) =>
    q === ''
      ? true
      : `${txn.time} ${txn.label} ${txn.mode} ${txn.amount} ${txn.status}`
          .toLowerCase()
          .includes(q),
  )

  const salesValue = isLive && live.salesTotal !== null ? money(live.salesTotal) : '—'
  const litresValue =
    isLive && live.litresTotal !== null ? live.litresTotal.toLocaleString('en-IN') : '—'
  const litresDetail = isLive ? (live.litresSplit ?? 'From closed shifts') : 'No sales recorded'
  const cashValue = isLive && live.cashCollected !== null ? money(live.cashCollected) : '—'
  const cashShare =
    isLive && live.cashCollected !== null && live.salesTotal
      ? `${((live.cashCollected / live.salesTotal) * 100).toFixed(1)}% of sales`
      : 'No cash collections recorded today'
  const heroEyebrow = `${isLive ? 'Live' : 'Offline'} · ${station.code}`

  return (
    <>
      <div className="heading">
        <div>
          <h1>
            {session ? `${greeting()}, ${session.employee.name.split(' ')[0]}` : 'Station overview'}
          </h1>
          <div className="sub">
            {session
              ? `Station ${session.station.code} · signed in as ${session.employee.code} (${session.employee.role})`
              : `${station.name} · sign in to load live station data.`}
          </div>
        </div>
        <div className="actions">
          <Link className="btn" to="/reports">
            ⇩ Exports
          </Link>
          <button className="btn primary" onClick={() => navigate('/shifts')}>
            ＋ Close a shift
          </button>
        </div>
      </div>

      {!isLive && (
        <div className="notice">
          ⓘ <b>Offline:</b>{' '}
          {session
            ? 'backend not reachable or no data recorded yet — figures appear after the station saves to the server.'
            : 'sign in to load sales, collections and shift data from the station.'}
        </div>
      )}

      <div className="hero">
        <div>
          <span className="hero-eyebrow">{heroEyebrow}</span>
          <div className="hero-value">{salesValue}</div>
          <div className="hero-sub">
            {isLive ? 'Closed shifts and recorded sales only' : 'No sales recorded today'}
          </div>
        </div>
        <div className="hero-stats">
          <div className="hero-stat">
            <b>{litresValue} L</b>
            <span>{litresDetail}</span>
          </div>
          <div className="hero-stat">
            <b>{cashValue}</b>
            <span>{cashShare}</span>
          </div>
          <div className="hero-stat">
            <b>—</b>
            <span>Credit dues are on the Credit ledger</span>
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="cardhead">
          <h3>Collection mix today</h3>
          <span className="small">{isLive ? 'Live · API' : 'No data yet'}</span>
        </div>
        {mixList.length > 0 ? (
          <div className="kpirow">
            {mixList.map((row) => (
              <div className="kpi" key={row.mode}>
                <span>{row.mode}</span>
                <b>{row.amount}</b>
                <span className="small">{row.share} of collections</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="small">No collections recorded today.</p>
        )}
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="cardhead">
          <h3>Shift status</h3>
          <span className={isLive ? 'pill blue' : 'pill amber'}>
            {isLive ? 'Live' : 'No data yet'}
          </span>
        </div>
        <p className="small" style={{ marginBottom: 10 }}>
          Open drafts and closed shifts are on the Shift &amp; readings page.
        </p>
        <Link to="/shifts" className="btn block">
          View shift register →
        </Link>
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
                    {!session
                      ? 'Sign in to see recent sales.'
                      : txnList.length === 0
                        ? 'No transactions recorded yet — close a shift or record a sale.'
                        : `No transactions match “${txnQuery}”.`}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
