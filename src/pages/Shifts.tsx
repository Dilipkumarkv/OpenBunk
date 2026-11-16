import { useCallback, useEffect, useMemo, useState, type ChangeEvent } from 'react'
import { useToast } from '../components/toastContext'
import { useAuth } from '../components/authContext'
import { getJson, postJson, putJson, ApiHttpError, ApiOfflineError } from '../lib/api'
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
// When signed in, Validate/Close also round-trip the backend (server is authoritative).
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

interface NozzleIds {
  petrol: string
  diesel: string
}

interface ServerIssue {
  field: string
  message: string
}

export default function Shifts() {
  const toast = useToast()
  const { session } = useAuth()
  const [inputs, setInputs] = useState<ShiftValidationInput>(INITIAL_INPUTS)
  const [issues, setIssues] = useState<ValidationIssue[]>([])
  const [serverIssues, setServerIssues] = useState<ServerIssue[]>([])
  const [rollover, setRollover] = useState({
    petrol: false,
    diesel: false,
    petrolValue: '100000',
    dieselValue: '100000',
  })
  const [nozzleIds, setNozzleIds] = useState<NozzleIds | null>(null)
  const [draftId, setDraftId] = useState<string | null>(null)
  const [closingPin, setClosingPin] = useState('')
  const [confirmingClose, setConfirmingClose] = useState(false)
  const [closedInfo, setClosedInfo] = useState<{ revenue: string; litres: string } | null>(null)
  const [busy, setBusy] = useState(false)

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

  // Fetch nozzle ids once signed in (needed to sync readings to the API)
  useEffect(() => {
    if (!session) {
      setNozzleIds(null)
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        const nozzles = await getJson<Array<{ id: string; label: string }>>('/api/v1/nozzles')
        if (cancelled) return
        const petrol = nozzles.find((n) => n.label.toUpperCase() === 'P1')
        const diesel = nozzles.find((n) => n.label.toUpperCase() === 'D1')
        setNozzleIds(petrol && diesel ? { petrol: petrol.id, diesel: diesel.id } : null)
      } catch {
        if (!cancelled) toast('Backend not reachable — Shifts stays in local demo mode.')
      }
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session])

  // Lazily find or create this afternoon's draft shift
  const ensureDraft = useCallback(async (): Promise<string | null> => {
    if (draftId) return draftId
    if (!session) return null
    const drafts = await getJson<Array<{ id: string; kind: string }>>(
      '/api/v1/shifts?status=draft&kind=afternoon&limit=1',
    )
    if (drafts.length > 0) {
      setDraftId(drafts[0].id)
      return drafts[0].id
    }
    const created = await postJson<{ id: string }>('/api/v1/shifts', { kind: 'afternoon' })
    setDraftId(created.id)
    return created.id
  }, [draftId, session])

  const readingsPayload = useCallback(() => {
    if (!nozzleIds) return null
    return {
      readings: [
        {
          nozzle_id: nozzleIds.petrol,
          opening_litres: inputs.petrolOpening || '0',
          closing_litres: inputs.petrolClosing || '0',
          unit_price: inputs.petrolPrice || '0',
        },
        {
          nozzle_id: nozzleIds.diesel,
          opening_litres: inputs.dieselOpening || '0',
          closing_litres: inputs.dieselClosing || '0',
          unit_price: inputs.dieselPrice || '0',
        },
      ],
    }
  }, [
    inputs.petrolOpening,
    inputs.petrolClosing,
    inputs.petrolPrice,
    inputs.dieselOpening,
    inputs.dieselClosing,
    inputs.dieselPrice,
    nozzleIds,
  ])

  const syncToApi = useCallback(async (): Promise<string | null> => {
    const id = await ensureDraft()
    const payload = readingsPayload()
    if (!id || !payload) return null
    await putJson(`/api/v1/shifts/${id}/readings`, payload)
    return id
  }, [ensureDraft, readingsPayload])

  const onValidate = async () => {
    const found = validateShiftReadings(inputs, {
      petrol: rollover.petrol,
      diesel: rollover.diesel,
      petrolRolloverValue: Number(rollover.petrolValue),
      dieselRolloverValue: Number(rollover.dieselValue),
    })
    setIssues(found)

    if (session) {
      setBusy(true)
      try {
        const id = await syncToApi()
        if (id) {
          const server = await postJson<{ valid: boolean; issues: ServerIssue[] }>(
            `/api/v1/shifts/${id}/validate`,
            {
              rollover: {
                petrol: rollover.petrol,
                diesel: rollover.diesel,
                petrol_rollover_value: rollover.petrol ? rollover.petrolValue : undefined,
                diesel_rollover_value: rollover.diesel ? rollover.dieselValue : undefined,
              },
            },
          )
          setServerIssues(server.issues)
          toast(
            server.valid && found.length === 0
              ? 'Validation passed (server + local agree).'
              : `Validation found issue(s): ${server.issues.length + found.length}.`,
          )
          return
        }
      } catch (error) {
        if (error instanceof ApiHttpError) {
          toast(`Backend rejected the readings (${error.status}). Local check shown below.`)
        } else {
          toast('Backend not reachable — showing local validation only.')
        }
      } finally {
        setBusy(false)
      }
    }

    toast(
      found.length === 0
        ? 'Validation passed: readings checked.'
        : `Validation found ${found.length} issue(s) — see details below.`,
    )
  }

  const onSaveDraft = async () => {
    if (!session) {
      toast('Demo only: draft is not persisted.')
      return
    }
    setBusy(true)
    try {
      await syncToApi()
      toast('Draft saved to the OpenBunk API.')
    } catch {
      toast('Backend not reachable — draft kept locally only.')
    } finally {
      setBusy(false)
    }
  }

  const onConfirmClose = async () => {
    if (!session) return
    setBusy(true)
    try {
      const id = await syncToApi()
      if (!id) throw new ApiOfflineError()
      const result = await postJson<{
        status: string
        revenue_total: string
        total_litres: string
      }>(
        `/api/v1/shifts/${id}/close`,
        {
          rollover: {
            petrol: rollover.petrol,
            diesel: rollover.diesel,
            petrol_rollover_value: rollover.petrol ? rollover.petrolValue : undefined,
            diesel_rollover_value: rollover.diesel ? rollover.dieselValue : undefined,
          },
        },
        {
          'Idempotency-Key': crypto.randomUUID(),
          'X-Reauth-Pin': closingPin,
        },
      )
      setClosedInfo({ revenue: result.revenue_total, litres: result.total_litres })
      setConfirmingClose(false)
      setClosingPin('')
      toast(`Shift closed on API — revenue ${money(Number(result.revenue_total))}.`)
    } catch (error) {
      if (error instanceof ApiHttpError) {
        if (error.status === 401) toast('PIN rejected — close aborted.')
        else if (error.status === 409) toast('Shift already closed.')
        else if (error.status === 422) toast('Server validation failed — check readings.')
        else toast(`Close failed (${error.status}).`)
      } else {
        toast('Backend not reachable — close aborted. No data was written.')
      }
    } finally {
      setBusy(false)
    }
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
          <button className="btn" onClick={() => window.print()}>
            ⎙ Print
          </button>
        </div>
      </div>

      <div className="notice">
        Assisted entry: enter opening and closing totalizers. Sales volume and value are calculated
        locally; collections are reconciled against expected sales.
        {session
          ? ' Signed in — readings persist to the OpenBunk API.'
          : ' Not signed in — nothing persists.'}
      </div>

      {closedInfo && (
        <div
          className="notice"
          style={{ background: '#e8f8f2', borderColor: '#bfe8d8', color: '#13865f' }}
        >
          ✓ Shift closed on the API. Revenue ₹ {Number(closedInfo.revenue).toLocaleString('en-IN')}{' '}
          · total {Number(closedInfo.litres).toLocaleString('en-IN')} L dispensed.
        </div>
      )}

      <div className="card">
        <div className="cardhead">
          <h3>Shift closing · Afternoon</h3>
          <span className={closedInfo ? 'pill green' : 'pill amber'}>
            {closedInfo ? 'Closed' : 'Draft'}
          </span>
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

        {serverIssues.length > 0 && (
          <div className="field-error" style={{ marginTop: 12 }} role="alert">
            <b>Server validation:</b>
            <ul style={{ margin: '6px 0 0 18px', padding: 0 }}>
              {serverIssues.map((issue, index) => (
                <li key={index}>
                  {issue.field}: {issue.message}
                </li>
              ))}
            </ul>
          </div>
        )}

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

        {confirmingClose && (
          <div className="reauth">
            <label htmlFor="reauth-pin">
              Confirm your PIN to close this shift (re-authentication)
            </label>
            <input
              id="reauth-pin"
              type="password"
              value={closingPin}
              onChange={(event) => setClosingPin(event.target.value)}
              autoFocus
              autoComplete="current-password"
            />
            <div className="formactions" style={{ marginTop: 10 }}>
              <button
                className="btn primary"
                onClick={() => void onConfirmClose()}
                disabled={closingPin.length < 4 || busy}
              >
                Confirm close shift
              </button>
              <button className="btn" onClick={() => setConfirmingClose(false)} disabled={busy}>
                Cancel
              </button>
            </div>
          </div>
        )}

        <div className="formactions">
          <button
            className="btn primary"
            onClick={() => void onSaveDraft()}
            disabled={busy || !!closedInfo}
          >
            Save draft
          </button>
          <button className="btn" onClick={() => void onValidate()} disabled={busy}>
            Validate readings
          </button>
          {!closedInfo &&
            (session ? (
              <button className="btn" onClick={() => setConfirmingClose(true)} disabled={busy}>
                Close shift
              </button>
            ) : (
              <button
                className="btn"
                onClick={() => toast('Demo: sign in to close a shift for real.')}
              >
                Close shift
              </button>
            ))}
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
