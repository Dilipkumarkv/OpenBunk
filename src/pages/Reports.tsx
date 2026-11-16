import { useEffect, useState } from 'react'
import { useToast } from '../components/toastContext'
import { useAuth } from '../components/authContext'
import { getJson, request } from '../lib/api'
import { money } from '../lib/format'
import { collectionBreakdown, dailySales, reportCatalogue } from '../data/sampleData'

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
        /* API unreachable — falls back to sample data */
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
      : dailySales

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
      : [...collectionBreakdown]

  const downloadCsv = async (type: 'sales' | 'collections') => {
    if (!session) {
      toast('Demo: sign in to download CSV exports.')
      return
    }
    try {
      const response = await request(`/api/v1/export.csv?type=${type}`)
      if (!response.ok) {
        toast(`Export failed (${response.status}).`)
        return
      }
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `openbunk-${type}.csv`
      a.click()
      URL.revokeObjectURL(url)
      toast(`Downloaded openbunk-${type}.csv`)
    } catch {
      toast('Backend not reachable — export not possible.')
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
          <button className="btn" onClick={() => void downloadCsv('sales')}>
            ⇩ Sales CSV
          </button>
          <button className="btn" onClick={() => void downloadCsv('collections')}>
            ⇩ Collections CSV
          </button>
        </div>
      </div>

      <div className="grid two">
        <div className="card">
          <div className="cardhead">
            <h3>Daily sales summary</h3>
            <span className={isLive ? 'pill green' : 'pill blue'}>
              {isLive ? 'Live · today' : 'Today'}
            </span>
          </div>
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
          {!isLive && (
            <p className="small" style={{ marginTop: 10 }}>
              Sample data (closed shifts appear here once signed in and closed).
            </p>
          )}
        </div>

        <div className="card">
          <div className="cardhead">
            <h3>Collection breakdown</h3>
            {isLive && <span className="pill green">Live</span>}
          </div>
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
                {collRows.length === 0 && (
                  <tr>
                    <td colSpan={3} className="emptyhint">
                      No collections recorded today.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="cardhead">
          <h3>Available report catalogue</h3>
          <span className="small">Prototype preview</span>
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
                    <button className="btn" onClick={() => toast(`${report.name} preview`)}>
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
