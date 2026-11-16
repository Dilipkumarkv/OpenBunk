import { useEffect, useRef, useState } from 'react'
import { useToast } from '../components/toastContext'
import { useAuth } from '../components/authContext'
import { getJson, request, ApiHttpError, ApiOfflineError } from '../lib/api'
import { money } from '../lib/format'
import { creditAccounts } from '../data/sampleData'
import { CREDIT_STATUS_LABEL, CREDIT_STATUS_TONE, creditLimitStatus } from '../domain/credit'

interface ApiCustomer {
  id: string
  account_code: string
  name: string
  credit_limit: string
  balance: string | null
}

interface CreditRow {
  customer: string
  account: string
  limit: string
  outstanding: string
  last: string
  ageing: string
  status: string
  tone: 'green' | 'amber' | 'red'
}

interface LiveCredit {
  owner: string
  rows: CreditRow[]
}

interface ImportSummary {
  validate_only: boolean
  created: number
  rows: Array<{ line: number; ok: boolean; error?: string; account_code?: string }>
  summary: { total: number; valid: number; invalid: number }
}

export default function Credit() {
  const toast = useToast()
  const { session } = useAuth()
  const [query, setQuery] = useState('')
  const [live, setLive] = useState<LiveCredit | null>(null)
  const [importPreview, setImportPreview] = useState<ImportSummary | null>(null)
  const [importing, setImporting] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!session) return
    let cancelled = false
    ;(async () => {
      try {
        const customers = await getJson<ApiCustomer[]>('/api/v1/credit/customers')
        if (cancelled) return
        setLive({
          owner: session.employee.code,
          rows: customers.map((c): CreditRow => {
            const limit = Number(c.credit_limit)
            const balance = Number(c.balance ?? 0)
            const statusEnum = creditLimitStatus(balance, limit)
            const status = CREDIT_STATUS_LABEL[statusEnum]
            const tone = CREDIT_STATUS_TONE[statusEnum]
            return {
              customer: c.name,
              account: c.account_code,
              limit: money(limit),
              outstanding: money(balance),
              last: '—',
              ageing: '—',
              status,
              tone,
            }
          }),
        })
      } catch {
        /* API unreachable — falls back to sample data */
      }
    })()
    return () => {
      cancelled = true
    }
  }, [session, refreshKey])

  const isLive = Boolean(session && live && live.owner === session.employee.code)
  const rows: CreditRow[] = isLive && live ? live.rows : [...creditAccounts]

  const q = query.trim().toLowerCase()
  const visible = rows.filter((account) =>
    q === ''
      ? true
      : `${account.customer} ${account.account} ${account.last} ${account.ageing}`
          .toLowerCase()
          .includes(q),
  )

  const uploadCsv = async (validateOnly: boolean) => {
    const file = fileRef.current?.files?.[0]
    if (!file) {
      toast('Choose a CSV file first (account_code,name,credit_limit).')
      return
    }
    setImporting(true)
    try {
      const form = new FormData()
      form.append('file', file)
      const response = await request(
        `/api/v1/credit/customers/import.csv?validate_only=${validateOnly}`,
        { method: 'POST', body: form, headers: {} },
      )
      if (!response.ok) {
        const text = (await response.text()).slice(0, 200)
        toast(`Import rejected (${response.status}): ${text}`)
        return
      }
      const body = (await response.json()) as ImportSummary
      setImportPreview(body)
      if (!validateOnly) {
        toast(`Imported ${body.created} customer(s). ${body.summary.invalid} row(s) skipped.`)
        setRefreshKey((k) => k + 1)
      }
    } catch (error) {
      if (error instanceof ApiHttpError) toast(`Import failed (${error.status}).`)
      else if (error instanceof ApiOfflineError)
        toast('Backend not reachable — import not possible.')
      else toast('Import failed.')
    } finally {
      setImporting(false)
    }
  }

  return (
    <>
      <div className="heading">
        <div>
          <h1>Credit ledger</h1>
          <div className="sub">Customer balances and account activity.</div>
        </div>
        <div className="actions">
          <button className="btn primary" onClick={() => toast('New customer form (prototype).')}>
            ＋ Add customer
          </button>
        </div>
      </div>

      {session && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="cardhead">
            <h3>Import customers (CSV)</h3>
            <span className="small">Columns: account_code,name,credit_limit · max 500 rows</span>
          </div>
          <div className="actions" style={{ alignItems: 'center' }}>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,text/csv"
              aria-label="Select customer CSV"
              style={{ maxWidth: 280 }}
            />
            <button className="btn" onClick={() => void uploadCsv(true)} disabled={importing}>
              Validate (dry run)
            </button>
            {importPreview?.validate_only && importPreview.summary.valid > 0 && (
              <button
                className="btn primary"
                onClick={() => void uploadCsv(false)}
                disabled={importing}
              >
                Commit {importPreview.summary.valid} valid row(s)
              </button>
            )}
          </div>
          {importPreview && (
            <p className="small" style={{ marginTop: 10 }}>
              {importPreview.validate_only ? 'Dry run:' : 'Import:'} {importPreview.summary.valid}{' '}
              valid · {importPreview.summary.invalid} invalid of {importPreview.summary.total}{' '}
              row(s)
              {importPreview.rows.some((r) => !r.ok) && (
                <>
                  {' '}
                  — first error: line {importPreview.rows.find((r) => !r.ok)?.line}:{' '}
                  {importPreview.rows.find((r) => !r.ok)?.error}
                </>
              )}
            </p>
          )}
        </div>
      )}

      <div className="grid stats">
        <div className="card">
          <div className="stat-top">Total outstanding</div>
          <div className="value">
            {isLive
              ? money(rows.reduce((s, r) => s + Number(r.outstanding.replace(/[^\d.-]/g, '')), 0))
              : '₹ 1,42,800'}
          </div>
          <div className="small">
            {isLive ? `${rows.length} account(s) · live` : 'Across 12 active accounts'}
          </div>
        </div>
        <div className="card">
          <div className="stat-top">Overdue</div>
          <div className="value">₹ 28,400</div>
          <div className="delta danger">4 accounts need follow-up</div>
        </div>
        <div className="card">
          <div className="stat-top">Credit sales today</div>
          <div className="value">₹ 18,650</div>
          <div className="small">7 transactions</div>
        </div>
        <div className="card">
          <div className="stat-top">Collections today</div>
          <div className="value">₹ 12,000</div>
          <div className="delta">3 receipts</div>
        </div>
      </div>

      <div className="card">
        <div className="cardhead">
          <h3>Customer accounts</h3>
          <input
            className="search"
            placeholder="Search customer…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label="Search customer"
          />
        </div>
        <div className="tablewrap">
          <table>
            <thead>
              <tr>
                <th>Customer</th>
                <th>Account</th>
                <th>Credit limit</th>
                <th>Outstanding</th>
                <th>Last transaction</th>
                <th>Ageing</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((account) => (
                <tr key={account.account}>
                  <td>
                    <b>{account.customer}</b>
                  </td>
                  <td>{account.account}</td>
                  <td>{account.limit}</td>
                  <td>{account.outstanding}</td>
                  <td>{account.last}</td>
                  <td>{account.ageing}</td>
                  <td>
                    <span className={`pill ${account.tone}`}>{account.status}</span>
                  </td>
                </tr>
              ))}
              {visible.length === 0 && (
                <tr>
                  <td colSpan={7} className="emptyhint">
                    {isLive
                      ? 'No customers yet — import a CSV above.'
                      : `No customers match “${query}”.`}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {!isLive && (
          <p className="small" style={{ marginTop: 10 }}>
            Sample data — sign in to see live balances and import.
          </p>
        )}
      </div>
    </>
  )
}
