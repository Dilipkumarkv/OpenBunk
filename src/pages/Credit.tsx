import { useState } from 'react'
import { useToast } from '../components/toastContext'
import { creditAccounts } from '../data/sampleData'

export default function Credit() {
  const toast = useToast()
  const [query, setQuery] = useState('')

  const q = query.trim().toLowerCase()
  const visible = creditAccounts.filter((account) =>
    q === ''
      ? true
      : `${account.customer} ${account.account} ${account.last}`.toLowerCase().includes(q),
  )

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

      <div className="grid stats">
        <div className="card">
          <div className="stat-top">Total outstanding</div>
          <div className="value">₹ 1,42,800</div>
          <div className="small">Across 12 active accounts</div>
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
        <table>
          <thead>
            <tr>
              <th>Customer</th>
              <th>Account</th>
              <th>Credit limit</th>
              <th>Outstanding</th>
              <th>Last transaction</th>
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
                <td>
                  <span className={`pill ${account.tone}`}>{account.status}</span>
                </td>
              </tr>
            ))}
            {visible.length === 0 && (
              <tr>
                <td colSpan={6} className="emptyhint">
                  No customers match “{query}”.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  )
}
