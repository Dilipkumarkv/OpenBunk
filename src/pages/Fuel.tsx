import { useToast } from '../components/toastContext'
import { fuelReceipts, tankRegister } from '../data/sampleData'

export default function Fuel() {
  const toast = useToast()

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
            onClick={() => toast('Fuel receipt form would open in full build.')}
          >
            ＋ Record fuel receipt
          </button>
        </div>
      </div>

      <div className="grid stats">
        <div className="card">
          <div className="stat-top">Petrol book stock</div>
          <div className="value">8,420 L</div>
          <div className="delta">Tank capacity 15,000 L</div>
        </div>
        <div className="card">
          <div className="stat-top">Diesel book stock</div>
          <div className="value">11,280 L</div>
          <div className="delta">Tank capacity 20,000 L</div>
        </div>
        <div className="card">
          <div className="stat-top">Last receipt</div>
          <div className="value value-sm">14 Nov</div>
          <div className="small">Petrol · 6,000 L</div>
        </div>
        <div className="card">
          <div className="stat-top">Stock variance</div>
          <div className="value">−18 L</div>
          <div className="delta warn">Pending dip reconciliation</div>
        </div>
      </div>

      <div className="card">
        <div className="cardhead">
          <h3>Tank register</h3>
          <span className="small">Illustrative stock</span>
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
              {tankRegister.map((tank) => (
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
            </tbody>
          </table>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="cardhead">
          <h3>Recent fuel receipts</h3>
          <button className="btn" onClick={() => toast('Receipt entry is a prototype action.')}>
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
              {fuelReceipts.map((receipt) => (
                <tr key={receipt.invoice}>
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
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
