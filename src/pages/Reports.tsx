import { useEffect, useState } from 'react'
import { useToast } from '../components/toastContext'
import { useAuth } from '../components/authContext'
import { getJson, request, ApiAuthError, ApiOfflineError } from '../lib/api'
import { money } from '../lib/format'

const reportCatalogue = [
  {
    name: 'Shift Sheet',
    category: 'Operations',
    description: 'Meter readings, volume, collections, variance',
  },
  {
    name: 'Fuel Stock Ledger',
    category: 'Inventory',
    description: 'Receipts, sales, book stock and dip',
  },
  { name: 'Credit Ageing', category: 'Finance', description: 'Outstanding balances by age bucket' },
  {
    name: 'Collection Register',
    category: 'Finance',
    description: 'Cash, UPI, card and credit totals',
  },
] as const

interface DailySales {
  date: string
  totals: Array<{ product: string; volume_litres: string; amount: string }>
  grand_total_amount: string
  grand_total_litres: string
}

interface Collections {
  slices: Array<{ mode: string; amount: string }>
  total: string
}

interface LiveReports {
  owner: string
  date: string
  sales: DailySales
  collections: Collections
}

export default function Reports() {
  const toast = useToast()
  const { session } = useAuth()
  const [live, setLive] = useState<LiveReports | null>(null)
  const [exportPin, setExportPin] = useState('')
  const [exporting, setExporting] = useState(false)

  const canExport = Boolean(
    session && ['owner', 'manager', 'accountant', 'auditor'].includes(session.employee.role),
  )

  useEffect(() => {
    if (!session) return
    let cancelled = false
    ;(async () => {
      const today = new Date().toISOString().slice(0, 10)
      try {
        const [daily, coll] = await Promise.all([
          getJson<DailySales>(`/api/v1/reports/daily-sales?date=${today}`),
          getJson<Collections>(`/api/v1/reports/collections?date=${today}`),
        ])
        if (!cancelled)
          setLive({ owner: session.employee.code, date: today, sales: daily, collections: coll })
      } catch {
        /* API unreachable — the page shows empty states until data loads */
      }
    })()
    return () => {
      cancelled = true
    }
  }, [session])

  const isLive = Boolean(session && live && live.owner === session.employee.code)
  const sales = isLive ? live!.sales : null
  const collections = isLive ? live!.collections : null

  const salesRows =
    isLive && sales
      ? [
          ...sales.totals.map((row) => ({
            product: row.product,
            volume: `${Number(row.volume_litres).toLocaleString('en-IN')} L`,
            value: money(Number(row.amount)),
            total: false,
          })),
          {
            product: 'Total',
            volume: `${Number(sales.grand_total_litres).toLocaleString('en-IN')} L`,
            value: money(Number(sales.grand_total_amount)),
            total: true,
          },
        ]
      : []

  const totalCollections = isLive && collections ? Number(collections.total) || 0 : 0
  const collRows =
    isLive && collections
      ? collections.slices.map((row) => ({
          mode: row.mode.charAt(0).toUpperCase() + row.mode.slice(1),
          amount: money(Number(row.amount)),
          share:
            totalCollections > 0
              ? `${((Number(row.amount) / totalCollections) * 100).toFixed(1)}%`
              : '0.0%',
          tone: 'blue',
        }))
      : []

  const downloadCsv = async (type: 'sales' | 'collections') => {
    if (!session) {
      toast('Sign in to download CSV exports.')
      return
    }
    if (!canExport) {
      toast('Your role cannot export CSV data.')
      return
    }
    if (exportPin.length < 6) {
      toast('Enter your 6+ digit PIN to authorize the export.')
      return
    }
    setExporting(true)
    try {
      const response = await request(
        `/api/v1/export.csv?type=${type}`,
        { headers: { 'X-Reauth-Pin': exportPin } },
        { retryAuth: false },
      )
      if (!response.ok) {
        if (response.status === 401) toast('PIN rejected — export not downloaded.')
        else if (response.status === 429) toast('Re-authentication is locked — try again later.')
        else if (response.status === 403) toast('Your role cannot export this data.')
        else toast(`Export failed (${response.status}).`)
        return
      }
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `deepbnk-${type}.csv`
      a.click()
      URL.revokeObjectURL(url)
      setExportPin('')
      toast(`Downloaded deepbnk-${type}.csv from the server.`)
    } catch (error) {
      if (error instanceof ApiAuthError) toast('Session expired — sign in again to export.')
      else if (error instanceof ApiOfflineError)
        toast('Backend not reachable — export not possible.')
      else toast('Export failed — nothing was downloaded.')
    } finally {
      setExporting(false)
    }
  }

  return (
    <>
      <div className="heading">
        <div>
          <h1>Reports</h1>
          <div className="sub">Operational and financial summaries.</div>
        </div>
        <div className="actions">
          <input
            type="password"
            inputMode="numeric"
            aria-label="PIN for CSV export"
            placeholder="Export PIN"
            value={exportPin}
            onChange={(event) => setExportPin(event.target.value)}
            disabled={!canExport || exporting}
            style={{ maxWidth: 130 }}
          />
          <button
            className="btn"
            onClick={() => void downloadCsv('sales')}
            disabled={!canExport || exporting}
          >
            ⇩ Sales CSV
          </button>
          <button
            className="btn"
            onClick={() => void downloadCsv('collections')}
            disabled={!canExport || exporting}
          >
            ⇩ Collections CSV
          </button>
        </div>
      </div>

      {session && !canExport && (
        <div className="notice">
          ⓘ CSV export requires an owner, manager, accountant or auditor. Your role can view the
          reports but not export them.
        </div>
      )}

      <div className="grid two">
        <div className="card">
          <div className="cardhead">
            <h3>Daily sales summary</h3>
            <span className={isLive ? 'pill green' : 'pill blue'}>
              {isLive ? 'Live · today' : 'Today'}
            </span>
          </div>
          {salesRows.length === 0 ? (
            <p className="small emptyhint">
              {isLive
                ? 'No sales recorded today.'
                : session
                  ? 'No sales data loaded.'
                  : 'Sign in to load today’s sales.'}
            </p>
          ) : (
            <div className="tablewrap">
              <table>
                <tbody>
                  {salesRows.map((row) =>
                    'total' in row && row.total ? (
                      <tr key={row.product}>
                        <td>
                          <b>{row.product}</b>
                        </td>
                        <td className="right">
                          <b>{row.volume}</b>
                        </td>
                        <td className="right">
                          <b>{row.value}</b>
                        </td>
                      </tr>
                    ) : (
                      <tr key={row.product}>
                        <td>{row.product}</td>
                        <td className="right">{row.volume}</td>
                        <td className="right">{row.value}</td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="card">
          <div className="cardhead">
            <h3>Collection breakdown</h3>
            {isLive && <span className="pill green">Live</span>}
          </div>
          {collRows.length === 0 ? (
            <p className="small emptyhint">
              {isLive
                ? 'No collections recorded today.'
                : session
                  ? 'No collection data loaded.'
                  : 'Sign in to load today’s collections.'}
            </p>
          ) : (
            <div className="tablewrap">
              <table>
                <tbody>
                  {collRows.map((row) => (
                    <tr key={row.mode}>
                      <td>{row.mode}</td>
                      <td className="right">{row.amount}</td>
                      <td className="right">
                        <span className={`pill ${row.tone}`}>{row.share}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="cardhead">
          <h3>Available report catalogue</h3>
          <span className="small">Report catalogue</span>
        </div>
        <div className="tablewrap">
          <table>
            <thead>
              <tr>
                <th>Report</th>
                <th>Category</th>
                <th>Description</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {reportCatalogue.map((report) => (
                <tr key={report.name}>
                  <td>{report.name}</td>
                  <td>{report.category}</td>
                  <td>{report.description}</td>
                  <td>
                    <button
                      className="btn"
                      onClick={() => toast(`${report.name} is not available yet.`)}
                    >
                      Open
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
