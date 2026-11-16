import { useMemo, useState, type ChangeEvent } from 'react'
import { useToast } from '../components/toastContext'
import { computeShiftTotals, parseMeterReadingOrZero } from '../domain/shift'
import {
  validateShiftReadings,
  type ShiftValidationInput,
  type ValidationIssue,
} from '../domain/validation'
import { reconcileCollections } from '../domain/reconcile'
import { money } from '../lib/format'

// Number-input behavior (decided in Phase 03):
// - Inputs keep raw strings, so clearing a field does NOT snap to 0.
// - Live math is lenient: invalid/empty input is treated as 0 while typing.
// - "Validate readings" is strict: empty/negative/closing<opening/zero price
//   are reported as human-readable issues, inline.
const INITIAL_INPUTS: ShiftValidationInput = {
  petrolOpening: '12450',
  petrolClosing: '12780',
  dieselOpening: '22500',
  dieselClosing: '22920',
  petrolPrice: '102.50',
  dieselPrice: '89.50',
  cashCollected: '25000',
  upiCollected: '32000',
}

const FIELD_IDS: Record<keyof ShiftValidationInput, string> = {
  petrolOpening: 'p1o',
  petrolClosing: 'p1c',
  dieselOpening: 'd1o',
  dieselClosing: 'd1c',
  petrolPrice: 'pp',
  dieselPrice: 'dp',
  cashCollected: 'cash',
  upiCollected: 'upi',
}

export default function Shifts() {
  const toast = useToast()
  const [inputs, setInputs] = useState<ShiftValidationInput>(INITIAL_INPUTS)
  const [issues, setIssues] = useState<ValidationIssue[]>([])
  // Explicit rollover authorization — never inferred from readings.
  const [rollover, setRollover] = useState({
    petrol: false,
    diesel: false,
    petrolValue: '100000',
    dieselValue: '100000',
  })

  const onField = (field: keyof ShiftValidationInput) => (event: ChangeEvent<HTMLInputElement>) =>
    setInputs((prev) => ({ ...prev, [field]: event.target.value }))

  const parsedRollover = useMemo(
    () => ({
      petrol: rollover.petrol ? Number(rollover.petrolValue) : undefined,
      diesel: rollover.diesel ? Number(rollover.dieselValue) : undefined,
    }),
    [rollover],
  )

  const totals = useMemo(
    () =>
      computeShiftTotals(
        {
          petrolOpening: parseMeterReadingOrZero(inputs.petrolOpening),
          petrolClosing: parseMeterReadingOrZero(inputs.petrolClosing),
          dieselOpening: parseMeterReadingOrZero(inputs.dieselOpening),
          dieselClosing: parseMeterReadingOrZero(inputs.dieselClosing),
          petrolPrice: parseMeterReadingOrZero(inputs.petrolPrice),
          dieselPrice: parseMeterReadingOrZero(inputs.dieselPrice),
        },
        { petrolValue: parsedRollover.petrol, dieselValue: parsedRollover.diesel },
      ),
    [inputs, parsedRollover],
  )

  const reconciliation = useMemo(
    () =>
      reconcileCollections(totals.totalValue, [
        parseMeterReadingOrZero(inputs.cashCollected),
        parseMeterReadingOrZero(inputs.upiCollected),
      ]),
    [totals.totalValue, inputs.cashCollected, inputs.upiCollected],
  )

  const onValidate = () => {
    const found = validateShiftReadings(inputs, {
      petrol: rollover.petrol,
      diesel: rollover.diesel,
      petrolRolloverValue: Number(rollover.petrolValue),
      dieselRolloverValue: Number(rollover.dieselValue),
    })
    setIssues(found)
    toast(
      found.length === 0
        ? 'Validation passed: readings checked.'
        : `Validation found ${found.length} issue(s) — see details below.`,
    )
  }

  const fieldIssue = (field: keyof ShiftValidationInput) =>
    issues.find((issue) => issue.field === field)?.message

  const field = (id: keyof ShiftValidationInput, label: string, type: 'number' = 'number') => {
    const message = fieldIssue(id)
    return (
      <div className="field">
        <label htmlFor={FIELD_IDS[id]}>{label}</label>
        <input
          id={FIELD_IDS[id]}
          type={type}
          inputMode="decimal"
          value={inputs[id]}
          onChange={onField(id)}
          aria-invalid={message ? true : undefined}
          aria-describedby={message ? `${FIELD_IDS[id]}-error` : undefined}
        />
        {message && (
          <div className="field-error" id={`${FIELD_IDS[id]}-error`}>
            {message}
          </div>
        )}
      </div>
    )
  }

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
        locally; collections are reconciled against expected sales.
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
          {field('petrolOpening', 'Petrol P1 opening (L)')}
          {field('petrolClosing', 'Petrol P1 closing (L)')}
          {field('dieselOpening', 'Diesel D1 opening (L)')}
          {field('dieselClosing', 'Diesel D1 closing (L)')}
          {field('petrolPrice', 'Petrol price (₹/L)')}
          {field('dieselPrice', 'Diesel price (₹/L)')}
          {field('cashCollected', 'Cash collected (₹)')}
          {field('upiCollected', 'UPI / card collected (₹)')}
        </div>

        <fieldset className="rollover">
          <legend>Meter rollover / reset (authorized only)</legend>
          <p className="small">
            Authorize only with a reason recorded. Rollover value is the totalizer wrap value (meter
            returns to 0 above it), e.g. 100000 for a 5-digit meter.
          </p>
          <div className="formgrid">
            <div className="field">
              <label className="check">
                <input
                  type="checkbox"
                  checked={rollover.petrol}
                  onChange={(event) =>
                    setRollover((prev) => ({ ...prev, petrol: event.target.checked }))
                  }
                />
                Petrol P1 rollover authorized
              </label>
              <input
                aria-label="Petrol rollover value"
                type="number"
                value={rollover.petrolValue}
                disabled={!rollover.petrol}
                onChange={(event) =>
                  setRollover((prev) => ({ ...prev, petrolValue: event.target.value }))
                }
              />
            </div>
            <div className="field">
              <label className="check">
                <input
                  type="checkbox"
                  checked={rollover.diesel}
                  onChange={(event) =>
                    setRollover((prev) => ({ ...prev, diesel: event.target.checked }))
                  }
                />
                Diesel D1 rollover authorized
              </label>
              <input
                aria-label="Diesel rollover value"
                type="number"
                value={rollover.dieselValue}
                disabled={!rollover.diesel}
                onChange={(event) =>
                  setRollover((prev) => ({ ...prev, dieselValue: event.target.value }))
                }
              />
            </div>
          </div>
        </fieldset>
        <div className="formactions">
          <button
            className="btn primary"
            onClick={() => toast('Demo only: draft is not persisted.')}
          >
            Save draft
          </button>
          <button className="btn" onClick={onValidate}>
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

      <div className="card" style={{ marginTop: 16 }}>
        <div className="cardhead">
          <h3>Reconciliation preview</h3>
          <span
            className={`pill ${
              reconciliation.status === 'balanced'
                ? 'green'
                : reconciliation.status === 'over'
                  ? 'blue'
                  : 'red'
            }`}
          >
            {reconciliation.status === 'balanced'
              ? 'Balanced'
              : reconciliation.status === 'over'
                ? 'Collected more'
                : 'Collected short'}
          </span>
        </div>
        <div className="tablewrap">
          <table>
            <tbody>
              <tr>
                <td>Expected sales (petrol + diesel)</td>
                <td className="right">{money(reconciliation.expected)}</td>
              </tr>
              <tr>
                <td>Collections (cash + UPI/card)</td>
                <td className="right">{money(reconciliation.collected)}</td>
              </tr>
              <tr>
                <td>
                  <b>Variance</b>
                </td>
                <td className="right">
                  <b>
                    {reconciliation.variance >= 0 ? '+' : ''}
                    {money(reconciliation.variance)}
                  </b>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
