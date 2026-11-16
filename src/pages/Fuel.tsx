import { useEffect, useState } from 'react'
import { useToast } from '../components/toastContext'
import { useAuth } from '../components/authContext'
import { getJson } from '../lib/api'

interface ApiTank {
  id: string
  label: string
  product_id: string
  capacity_litres: string
  opening_book_litres: string
}

interface ApiProduct {
  id: string
  code: string
  name: string
}

interface ApiStock {
  tank_id: string
  book_stock_litres: string
}

interface ApiReceipt {
  id: string
  tank_id: string
  product_id: string
  quantity_litres: string
  supplier: string | null
  invoice_no: string | null
  received_at: string
}

interface TankRow {
  tank: string
  product: string
  capacity: string
  book: string
  dip: string
  variance: string
  tone: 'amber' | 'green'
  level: string
}

interface ReceiptRow {
  date: string
  supplier: string
  product: string
  qty: string
  invoice: string
  status: string
  tone: 'green' | 'amber' | 'blue'
}

interface LiveFuel {
  owner: string
  tanks: TankRow[]
  receipts: ReceiptRow[]
}

export default function Fuel() {
  const toast = useToast()
  const { session } = useAuth()
  const [live, setLive] = useState<LiveFuel | null>(null)

  useEffect(() => {
    if (!session) return
    let cancelled = false
    ;(async () => {
      try {
        const [tanks, products, receipts] = await Promise.all([
          getJson<ApiTank[]>('/api/v1/tanks'),
          getJson<ApiProduct[]>('/api/v1/fuel-products'),
          getJson<ApiReceipt[]>('/api/v1/fuel-receipts'),
        ])
        const stocks = await Promise.all(
          tanks.map((t) => getJson<ApiStock>(`/api/v1/tanks/${t.id}/stock`).catch(() => null)),
        )
        if (cancelled) return
        const productName = (id: string) => products.find((p) => p.id === id)?.name ?? '—'
        setLive({
          owner: session.employee.code,
          tanks: tanks.map((t, i) => {
            const book = Number(stocks[i]?.book_stock_litres ?? t.opening_book_litres)
            const capacity = Number(t.capacity_litres)
            return {
              tank: t.label,
              product: productName(t.product_id),
              capacity: `${capacity.toLocaleString('en-IN')} L`,
              book: `${book.toLocaleString('en-IN')} L`,
              dip: '—',
              variance: '—',
              tone: 'amber',
              level: capacity > 0 ? `${Math.round((book / capacity) * 100)}%` : '—',
            }
          }),
          receipts: receipts.slice(0, 10).map((r) => ({
            date: new Date(r.received_at).toLocaleDateString('en-IN', {
              day: '2-digit',
              month: 'short',
              year: 'numeric',
            }),
            supplier: r.supplier ?? '—',
            product: productName(r.product_id),
            qty: `${Number(r.quantity_litres).toLocaleString('en-IN')} L`,
            invoice: r.invoice_no ?? '—',
            status: 'Posted',
            tone: 'green',
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

  const isLive = Boolean(session && live && live.owner === session.employee.code)
  const tanks: TankRow[] = isLive && live ? live.tanks : []
  const receipts: ReceiptRow[] = isLive && live ? live.receipts : []
  const petrolTank = tanks.find((t) => t.product.toLowerCase().includes('petrol'))
  const dieselTank = tanks.find((t) => t.product.toLowerCase().includes('diesel'))

  return (
    <>
      <div className="heading">
        <div>
          <h1>Fuel & stock</h1>
          <div className="sub">Tank position, book stock and receipts.</div>
        </div>
        <div className="actions">
          <button
            className="btn primary"
            onClick={() => toast('Fuel receipt entry is not available yet.')}
          >
            ＋ Record fuel receipt
          </button>
        </div>
      </div>

      <div className="grid stats">
        <div className="card">
          <div className="stat-top">Petrol book stock</div>
          <div className="value">{petrolTank?.book ?? '—'}</div>
          <div className="delta">
            {petrolTank ? `Tank capacity ${petrolTank.capacity}` : 'No petrol tank configured'}
          </div>
        </div>
        <div className="card">
          <div className="stat-top">Diesel book stock</div>
          <div className="value">{dieselTank?.book ?? '—'}</div>
          <div className="delta">
            {dieselTank ? `Tank capacity ${dieselTank.capacity}` : 'No diesel tank configured'}
          </div>
        </div>
        <div className="card">
          <div className="stat-top">Last receipt</div>
          <div className="value value-sm">{receipts[0]?.date ?? '—'}</div>
          <div className="small">
            {receipts[0] ? `${receipts[0].product} · ${receipts[0].qty}` : 'No receipts recorded'}
          </div>
        </div>
        <div className="card">
          <div className="stat-top">Stock variance</div>
          <div className="value">—</div>
          <div className="delta warn">Dip readings not recorded</div>
        </div>
      </div>

      <div className="card">
        <div className="cardhead">
          <h3>Tank register</h3>
          <span className="small">
            {isLive ? 'Live · stock derived from movements' : 'No data yet'}
          </span>
        </div>
        <div className="tablewrap">
          <table>
            <thead>
              <tr>
                <th>Tank</th>
                <th>Product</th>
                <th>Capacity</th>
                <th>Book stock</th>
                <th>Physical dip</th>
                <th>Variance</th>
                <th>Level</th>
              </tr>
            </thead>
            <tbody>
              {tanks.map((tank) => (
                <tr key={tank.tank}>
                  <td>{tank.tank}</td>
                  <td>{tank.product}</td>
                  <td>{tank.capacity}</td>
                  <td>{tank.book}</td>
                  <td>{tank.dip}</td>
                  <td>
                    <span className={`pill ${tank.tone}`}>{tank.variance}</span>
                  </td>
                  <td>{tank.level}</td>
                </tr>
              ))}
              {tanks.length === 0 && (
                <tr>
                  <td colSpan={7} className="emptyhint">
                    {isLive ? 'No tanks configured yet.' : 'Sign in to load the tank register.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="cardhead">
          <h3>Recent fuel receipts</h3>
          <button className="btn" onClick={() => toast('Receipt entry is not available yet.')}>
            ＋ New receipt
          </button>
        </div>
        <div className="tablewrap">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Supplier</th>
                <th>Product</th>
                <th>Quantity</th>
                <th>Invoice</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {receipts.map((receipt) => (
                <tr key={receipt.invoice + receipt.date}>
                  <td>{receipt.date}</td>
                  <td>{receipt.supplier}</td>
                  <td>{receipt.product}</td>
                  <td>{receipt.qty}</td>
                  <td>{receipt.invoice}</td>
                  <td>
                    <span className={`pill ${receipt.tone}`}>{receipt.status}</span>
                  </td>
                </tr>
              ))}
              {receipts.length === 0 && (
                <tr>
                  <td colSpan={6} className="emptyhint">
                    {isLive ? 'No fuel receipts recorded yet.' : 'Sign in to load fuel receipts.'}
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
