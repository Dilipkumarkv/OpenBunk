import { useMemo, useState, type ChangeEvent } from 'react'
import { useToast } from '../components/toastContext'
import { money } from '../lib/format'
import { computeShiftTotals } from '../lib/shiftCalc'

const INITIAL = {
  petrolOpening: 12450,
  petrolClosing: 12780,
  dieselOpening: 22500,
  dieselClosing: 22920,
  petrolPrice: 102.5,
  dieselPrice: 89.5,
}

type Field = keyof typeof INITIAL

export default function Shifts() {
  const toast = useToast()
  const [readings, setReadings] = useState(INITIAL)

  const onNumber = (field: Field) => (event: ChangeEvent<HTMLInputElement>) =>
    setReadings((prev) => ({ ...prev, [field]: Number(event.target.value) }))

  const totals = useMemo(() => computeShiftTotals(readings), [readings])

  return (
    <>
      <div className="heading">
        <div>
          <h1>Shift & meter readings</h1>
          <div className="sub">Capture readings and reconcile a shift.</div>
        </div>
        <div className="actions">
          <button className="btn" onClick={() => toast('Shift register exported (demo).')}>
            Export shift sheet
          </button>
        </div>
      </div>

      <div className="notice">
        Assisted entry: enter opening and closing totalizers. Sales volume and value are calculated
        locally in this demo.
      </div>

      <div className="card">
        <div className="cardhead">
          <h3>Shift closing · Afternoon</h3>
          <span className="pill amber">Draft</span>
        </div>
        <div className="formgrid">
          <div className="field">
            <label htmlFor="shift">Shift</label>
            <select id="shift" defaultValue="afternoon">
              <option value="afternoon">Afternoon · 14:00–22:00</option>
              <option value="morning">Morning · 06:00–14:00</option>
              <option value="night">Night · 22:00–06:00</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="salesman">Salesman</label>
            <select id="salesman" defaultValue="kumar">
              <option value="kumar">Kumar (EMP-02)</option>
              <option value="ravi">Ravi (EMP-01)</option>
              <option value="manjunath">Manjunath (EMP-03)</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="p1o">Petrol P1 opening (L)</label>
            <input
              id="p1o"
              type="number"
              value={readings.petrolOpening}
              onChange={onNumber('petrolOpening')}
            />
          </div>
          <div className="field">
            <label htmlFor="p1c">Petrol P1 closing (L)</label>
            <input
              id="p1c"
              type="number"
              value={readings.petrolClosing}
              onChange={onNumber('petrolClosing')}
            />
          </div>
          <div className="field">
            <label htmlFor="d1o">Diesel D1 opening (L)</label>
            <input
              id="d1o"
              type="number"
              value={readings.dieselOpening}
              onChange={onNumber('dieselOpening')}
            />
          </div>
          <div className="field">
            <label htmlFor="d1c">Diesel D1 closing (L)</label>
            <input
              id="d1c"
              type="number"
              value={readings.dieselClosing}
              onChange={onNumber('dieselClosing')}
            />
          </div>
          <div className="field">
            <label htmlFor="pp">Petrol price (₹/L)</label>
            <input
              id="pp"
              type="number"
              value={readings.petrolPrice}
              onChange={onNumber('petrolPrice')}
            />
          </div>
          <div className="field">
            <label htmlFor="dp">Diesel price (₹/L)</label>
            <input
              id="dp"
              type="number"
              value={readings.dieselPrice}
              onChange={onNumber('dieselPrice')}
            />
          </div>
          <div className="field">
            <label htmlFor="cash">Cash collected (₹)</label>
            <input id="cash" type="number" defaultValue={25000} />
          </div>
          <div className="field">
            <label htmlFor="upi">UPI / card collected (₹)</label>
            <input id="upi" type="number" defaultValue={32000} />
          </div>
        </div>
        <div className="formactions">
          <button
            className="btn primary"
            onClick={() => toast('Shift saved as draft (demo only).')}
          >
            Save draft
          </button>
          <button
            className="btn"
            onClick={() => toast('Validation preview: readings checked (demo).')}
          >
            Validate readings
          </button>
          <button
            className="btn"
            onClick={() => toast('Demo: closing requires reconciliation in production.')}
          >
            Close shift
          </button>
        </div>
      </div>

      <div className="grid stats" style={{ marginTop: 16 }}>
        <div className="card">
          <div className="stat-top">Petrol volume</div>
          <div className="value">{totals.petrolVolume.toLocaleString('en-IN')} L</div>
          <div className="small">P1 meter difference</div>
        </div>
        <div className="card">
          <div className="stat-top">Petrol value</div>
          <div className="value">{money(totals.petrolValue)}</div>
          <div className="small">Volume × price</div>
        </div>
        <div className="card">
          <div className="stat-top">Diesel volume</div>
          <div className="value">{totals.dieselVolume.toLocaleString('en-IN')} L</div>
          <div className="small">D1 meter difference</div>
        </div>
        <div className="card">
          <div className="stat-top">Diesel value</div>
          <div className="value">{money(totals.dieselValue)}</div>
          <div className="small">Volume × price</div>
        </div>
      </div>
    </>
  )
}
