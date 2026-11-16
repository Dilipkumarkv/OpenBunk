import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent } from 'react'
import { useToast } from '../components/toastContext'
import { useAuth } from '../components/authContext'
import { ApiAuthError, ApiHttpError, ApiOfflineError, getJson, postJson, putJson } from '../lib/api'
import { clearShiftDraft, loadShiftDraft, saveShiftDraft, type ShiftDraft } from '../lib/draft'
import {
  computeNozzleTotals,
  parseMeterReading,
  parseMeterReadingOrZero,
  type NozzleReadingInput,
} from '../domain/shift'
import { validateNozzleDraft, type DraftIssue, type RolloverInputs } from '../domain/validation'
import { reconcileCollections } from '../domain/reconcile'
import { round2 } from '../domain/money'
import { money } from '../lib/format'

// Number-input behavior (decided in Phase 03):
// - Inputs keep raw strings, so clearing a field does NOT snap to 0.
// - Live math is lenient: invalid/empty input is treated as 0 while typing.
// - "Validate readings" is strict: empty/negative/closing<opening/missing price
//   are reported as human-readable issues, inline.
// When signed in, Save/Validate/Close round-trip the backend (server is authoritative).
// When signed out the nozzle catalog stays empty; the page asks the user to sign in.

type ShiftKind = 'morning' | 'afternoon' | 'night'

const SHIFT_KINDS: Array<{ value: ShiftKind; label: string }> = [
  { value: 'morning', label: 'Morning · 06:00–14:00' },
  { value: 'afternoon', label: 'Afternoon · 14:00–22:00' },
  { value: 'night', label: 'Night · 22:00–06:00' },
]

const COLLECTION_MODES = ['cash', 'upi', 'card', 'other'] as const
const COLLECTION_LABELS: Record<(typeof COLLECTION_MODES)[number], string> = {
  cash: 'Cash collected (₹)',
  upi: 'UPI collected (₹)',
  card: 'Card collected (₹)',
  other: 'Other collected (₹)',
}

interface ApiNozzle {
  id: string
  label: string
  tank_id: string
  product_id: string
  active: boolean
}

interface ApiProduct {
  id: string
  code: string
  name: string
}

interface ApiPrice {
  product_id: string
  product_code: string
  product_name: string
  unit_price: string
}

interface ApiShift {
  id: string
  employee_id: string
  kind: string
  business_date: string
  status: string
  opened_at: string
  closed_at: string | null
  revenue_total: string | null
  collections: Record<string, string> | null
  variance_amount: string | null
  variance_reason: string | null
  version: number
}

interface ApiReading {
  nozzle_id: string
  opening_litres: string
  closing_litres: string
  unit_price: string
}

interface ShiftDetail extends ApiShift {
  readings: ApiReading[]
}

interface NozzleRow {
  id: string
  label: string
  productId: string
  productCode: string
  productName: string
  /** Server-configured selling price, or '' when no price exists. */
  unitPrice: string
}

interface ServerIssue {
  field: string
  message: string
}

interface ClosedInfo {
  revenue: string
  litres: string
  variance: string
  reconciliation: string
}

const EMPTY_COLLECTIONS: Record<string, string> = { cash: '', upi: '', card: '', other: '' }
const EMPTY_ROLLOVER: RolloverInputs = {
  petrol: { authorized: false, value: '100000' },
  diesel: { authorized: false, value: '100000' },
}

function localDate(): string {
  return new Date().toISOString().slice(0, 10)
}

function isShiftKind(value: string): value is ShiftKind {
  return value === 'morning' || value === 'afternoon' || value === 'night'
}

function canOperate(role: string | undefined): boolean {
  return role === undefined || ['owner', 'manager', 'cashier'].includes(role)
}

function canCloseShift(role: string | undefined): boolean {
  return role === undefined || ['owner', 'manager'].includes(role)
}

export default function Shifts() {
  const toast = useToast()
  const { session } = useAuth()

  const [catalog, setCatalog] = useState<NozzleRow[]>([])
  const [catalogMode, setCatalogMode] = useState<'loading' | 'signed-out' | 'live' | 'error'>(
    'loading',
  )
  const [catalogError, setCatalogError] = useState<string | null>(null)
  const [shift, setShift] = useState<ShiftDetail | null>(null)
  const [shiftKind, setShiftKind] = useState<ShiftKind>('afternoon')
  const [readings, setReadings] = useState<Record<string, { opening: string; closing: string }>>({})
  const [collections, setCollections] = useState<Record<string, string>>(EMPTY_COLLECTIONS)
  const [rollover, setRollover] = useState<RolloverInputs>(EMPTY_ROLLOVER)
  const [issues, setIssues] = useState<DraftIssue[]>([])
  const [serverIssues, setServerIssues] = useState<ServerIssue[]>([])
  const [draftRestoredAt, setDraftRestoredAt] = useState<string | null>(null)
  const [conflict, setConflict] = useState(false)
  const [closedInfo, setClosedInfo] = useState<ClosedInfo | null>(null)
  const [busy, setBusy] = useState(false)
  const [ready, setReady] = useState(false)
  const [creditSales, setCreditSales] = useState<number | null>(null)

  const [confirmingClose, setConfirmingClose] = useState(false)
  const [closingPin, setClosingPin] = useState('')
  const [overrideReason, setOverrideReason] = useState('')
  const [approvalCode, setApprovalCode] = useState('')
  const [approvalPin, setApprovalPin] = useState('')
  const [needsOverride, setNeedsOverride] = useState(false)
  const [needsApproval, setNeedsApproval] = useState(false)
  const [closeError, setCloseError] = useState<string | null>(null)

  const dirtyRef = useRef(false)
  const idempotencyRef = useRef<{ key: string; fingerprint: string; shiftId: string } | null>(null)

  const role = session?.employee.role
  const editable = canOperate(role)
  const canClose = canCloseShift(role)
  const isClosed = Boolean(closedInfo || shift?.status === 'closed')

  const draftScope = useCallback(
    (date: string, kind: string) => {
      if (!session) return 'guest'
      return `${session.station.code}:${session.employee.code}:${date}:${kind}`
    },
    [session],
  )

  const applyDraft = useCallback((draft: ShiftDraft) => {
    setReadings((prev) => ({ ...prev, ...draft.inputs }))
    if (draft.collections) setCollections((prev) => ({ ...prev, ...draft.collections }))
    if (draft.rollover) setRollover((prev) => ({ ...prev, ...draft.rollover }))
    if (draft.shiftKind && isShiftKind(draft.shiftKind)) setShiftKind(draft.shiftKind)
    setDraftRestoredAt(draft.savedAt)
  }, [])

  const loadWorkspace = useCallback(async () => {
    setReady(false)
    dirtyRef.current = false
    setConflict(false)
    setServerIssues([])
    setIssues([])
    setCatalogError(null)

    if (!session) {
      setCatalog([])
      setCatalogMode('signed-out')
      setShift(null)
      setShiftKind('afternoon')
      setReadings({})
      setCollections(EMPTY_COLLECTIONS)
      setRollover(EMPTY_ROLLOVER)
      setDraftRestoredAt(null)
      setReady(true)
      return
    }

    setCatalogMode('loading')
    try {
      const [nozzles, products, prices, page] = await Promise.all([
        getJson<ApiNozzle[]>('/api/v1/nozzles'),
        getJson<ApiProduct[]>('/api/v1/fuel-products'),
        getJson<ApiPrice[]>('/api/v1/fuel-prices/current'),
        getJson<{ items: ApiShift[] }>('/api/v1/shifts?status=draft&limit=50'),
      ])

      const productById = new Map(products.map((product) => [product.id, product]))
      const priceByProduct = new Map(prices.map((price) => [price.product_id, price.unit_price]))
      const activeNozzles = nozzles.filter((nozzle) => nozzle.active)
      const rows: NozzleRow[] = activeNozzles.map((nozzle) => {
        const product = productById.get(nozzle.product_id)
        return {
          id: nozzle.id,
          label: nozzle.label,
          productId: nozzle.product_id,
          productCode: product?.code ?? 'unknown',
          productName: product?.name ?? 'Unknown fuel',
          unitPrice: priceByProduct.get(nozzle.product_id) ?? '',
        }
      })
      setCatalog(rows)
      setCatalogMode('live')

      const ownDrafts = page.items
        .filter((item) => item.employee_id === session.employee.id)
        .sort((a, b) => b.business_date.localeCompare(a.business_date))
      const detail = ownDrafts[0]
        ? await getJson<ShiftDetail>(`/api/v1/shifts/${ownDrafts[0].id}`)
        : null

      let activeDate = localDate()
      let activeKind: ShiftKind = 'afternoon'
      if (detail) {
        activeDate = detail.business_date
        activeKind = isShiftKind(detail.kind) ? detail.kind : 'afternoon'
        setShift(detail)
        setShiftKind(activeKind)
        const serverReadings: Record<string, { opening: string; closing: string }> = {}
        for (const reading of detail.readings) {
          serverReadings[reading.nozzle_id] = {
            opening: reading.opening_litres,
            closing: reading.closing_litres,
          }
        }
        setReadings(serverReadings)
        // The close uses the price stored when readings were recorded, not today's price.
        const storedPrices = new Map(
          detail.readings.map((reading) => [reading.nozzle_id, reading.unit_price]),
        )
        setCatalog(
          rows.map((row) => ({ ...row, unitPrice: storedPrices.get(row.id) ?? row.unitPrice })),
        )
      } else {
        setShift(null)
        setShiftKind('afternoon')
        setReadings({})
      }

      setCollections(EMPTY_COLLECTIONS)
      const rolloverCodes = Array.from(new Set(rows.map((row) => row.productCode))).filter(
        (code) => code === 'petrol' || code === 'diesel',
      )
      setRollover(
        rolloverCodes.length > 0
          ? Object.fromEntries(
              rolloverCodes.map((code) => [code, { authorized: false, value: '100000' }]),
            )
          : EMPTY_ROLLOVER,
      )
      setDraftRestoredAt(null)

      if (detail) {
        const local = loadShiftDraft(sessionStorage, draftScope(activeDate, activeKind))
        if (local) applyDraft(local)
      } else {
        // With no server draft, pick the most recent local draft for any kind today.
        const candidates = (['morning', 'afternoon', 'night'] as ShiftKind[])
          .map((kind) => ({
            kind,
            draft: loadShiftDraft(sessionStorage, draftScope(localDate(), kind)),
          }))
          .filter((entry): entry is { kind: ShiftKind; draft: ShiftDraft } => entry.draft !== null)
          .sort((a, b) => b.draft.savedAt.localeCompare(a.draft.savedAt))
        if (candidates[0]) {
          setShiftKind(candidates[0].kind)
          applyDraft(candidates[0].draft)
        }
      }
    } catch (error) {
      setCatalogMode('error')
      setCatalog([])
      setCatalogError(
        error instanceof ApiOfflineError
          ? 'Backend not reachable — no live catalog. Nothing on this page will be saved.'
          : error instanceof ApiHttpError
            ? `${error.message} (${error.status})`
            : 'Could not load the station catalog.',
      )
    } finally {
      setReady(true)
    }
  }, [applyDraft, draftScope, session])

  useEffect(() => {
    // Kick the load off just after paint. loadWorkspace resets form state before
    // fetching, which React prefers not to happen synchronously inside an effect.
    const timer = window.setTimeout(() => void loadWorkspace(), 0)
    return () => window.clearTimeout(timer)
  }, [loadWorkspace])
  // Keep an unsynced draft in this browser, scoped to station/employee/date/kind.
  useEffect(() => {
    if (!ready || !dirtyRef.current) return
    const draft: ShiftDraft = {
      inputs: readings,
      collections,
      rollover,
      shiftKind,
      savedAt: new Date().toISOString(),
    }
    saveShiftDraft(
      sessionStorage,
      draft,
      draftScope(shift?.business_date ?? localDate(), shift?.kind ?? shiftKind),
    )
  }, [ready, readings, collections, rollover, shiftKind, shift, draftScope])

  // Credit sales are not collections. The server excludes them at close; fetch them
  // for the preview when this role is allowed to list sales.
  const canSeeCreditSales = Boolean(
    session &&
    shift &&
    ['owner', 'manager', 'accountant', 'auditor'].includes(session.employee.role),
  )
  useEffect(() => {
    if (!canSeeCreditSales || !shift) return
    let cancelled = false
    ;(async () => {
      try {
        const sales = await getJson<
          Array<{ shift_id: string | null; tender: string; amount: string }>
        >('/api/v1/sales?tender=credit&limit=200')
        if (cancelled) return
        const total = sales
          .filter((sale) => sale.shift_id === shift.id)
          .reduce((sum, sale) => sum + parseMeterReadingOrZero(sale.amount), 0)
        setCreditSales(round2(total))
      } catch {
        if (!cancelled) setCreditSales(null)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [canSeeCreditSales, shift])
  const creditSalesForShift = canSeeCreditSales ? creditSales : null

  const rows: NozzleReadingInput[] = useMemo(
    () =>
      catalog.map((row) => ({
        nozzleId: row.id,
        label: row.label,
        productCode: row.productCode,
        productName: row.productName,
        opening: readings[row.id]?.opening ?? '',
        closing: readings[row.id]?.closing ?? '',
        unitPrice: row.unitPrice,
      })),
    [catalog, readings],
  )

  const rolloverValues = useMemo(() => {
    const values: Record<string, number | undefined> = {}
    for (const [code, authorization] of Object.entries(rollover)) {
      if (authorization.authorized)
        values[code] = parseMeterReading(authorization.value) ?? undefined
    }
    return values
  }, [rollover])

  const totals = useMemo(() => computeNozzleTotals(rows, rolloverValues), [rows, rolloverValues])

  const reconciliation = useMemo(() => {
    const collected = COLLECTION_MODES.map((mode) =>
      parseMeterReadingOrZero(collections[mode] ?? ''),
    )
    return reconcileCollections(totals.totalValue - (creditSalesForShift ?? 0), collected)
  }, [totals.totalValue, creditSalesForShift, collections])

  const productTotals = useMemo(() => {
    const grouped = new Map<
      string,
      { code: string; name: string; volume: number; value: number; nozzles: string[] }
    >()
    for (const line of totals.lines) {
      const entry = grouped.get(line.productCode) ?? {
        code: line.productCode,
        name: line.productName,
        volume: 0,
        value: 0,
        nozzles: [],
      }
      entry.volume += line.volume
      entry.value += line.value
      entry.nozzles.push(line.label)
      grouped.set(line.productCode, entry)
    }
    return Array.from(grouped.values()).map((entry) => ({
      ...entry,
      volume: round2(entry.volume),
      value: round2(entry.value),
    }))
  }, [totals])

  const rolloverProducts = useMemo(() => {
    const seen = new Map<string, string>()
    for (const row of catalog) {
      if (
        (row.productCode === 'petrol' || row.productCode === 'diesel') &&
        !seen.has(row.productCode)
      ) {
        seen.set(row.productCode, row.productName)
      }
    }
    return Array.from(seen.entries()).map(([code, name]) => ({ code, name }))
  }, [catalog])

  const rolloverPayload = useMemo(
    () => ({
      petrol: rollover.petrol?.authorized ?? false,
      diesel: rollover.diesel?.authorized ?? false,
      petrol_rollover_value: rollover.petrol?.authorized ? rollover.petrol.value : undefined,
      diesel_rollover_value: rollover.diesel?.authorized ? rollover.diesel.value : undefined,
    }),
    [rollover],
  )

  const onReading =
    (nozzleId: string, part: 'opening' | 'closing') => (event: ChangeEvent<HTMLInputElement>) => {
      dirtyRef.current = true
      setReadings((prev) => ({
        ...prev,
        [nozzleId]: {
          opening: prev[nozzleId]?.opening ?? '',
          closing: prev[nozzleId]?.closing ?? '',
          [part]: event.target.value,
        },
      }))
    }

  const onCollection = (mode: string) => (event: ChangeEvent<HTMLInputElement>) => {
    dirtyRef.current = true
    setCollections((prev) => ({ ...prev, [mode]: event.target.value }))
  }

  const onRolloverToggle = (code: string) => (event: ChangeEvent<HTMLInputElement>) => {
    dirtyRef.current = true
    setRollover((prev) => ({
      ...prev,
      [code]: { authorized: event.target.checked, value: prev[code]?.value ?? '100000' },
    }))
  }

  const onRolloverValue = (code: string) => (event: ChangeEvent<HTMLInputElement>) => {
    dirtyRef.current = true
    setRollover((prev) => ({
      ...prev,
      [code]: { authorized: prev[code]?.authorized ?? false, value: event.target.value },
    }))
  }

  const ensureDraft = useCallback(async (): Promise<ShiftDetail> => {
    if (shift) return shift
    const created = await postJson<ApiShift>('/api/v1/shifts', { kind: shiftKind })
    const detail: ShiftDetail = { ...created, readings: [] }
    setShift(detail)
    return detail
  }, [shift, shiftKind])

  const syncReadings = useCallback(async (): Promise<{ id: string; saved: number }> => {
    const current = await ensureDraft()
    const complete = rows.filter(
      (row) => parseMeterReading(row.opening) !== null && parseMeterReading(row.closing) !== null,
    )
    if (complete.length === 0) return { id: current.id, saved: 0 }

    const detail = await putJson<ShiftDetail>(`/api/v1/shifts/${current.id}/readings`, {
      expected_version: current.version,
      readings: complete.map((row) => ({
        nozzle_id: row.nozzleId,
        opening_litres: row.opening,
        closing_litres: row.closing,
      })),
    })
    setShift(detail)
    const storedPrices = new Map(
      detail.readings.map((reading) => [reading.nozzle_id, reading.unit_price]),
    )
    setCatalog((prev) =>
      prev.map((row) => ({ ...row, unitPrice: storedPrices.get(row.id) ?? row.unitPrice })),
    )
    return { id: detail.id, saved: complete.length }
  }, [ensureDraft, rows])

  const handleSaveError = (error: unknown) => {
    if (error instanceof ApiOfflineError) {
      toast(
        'Backend not reachable — the draft stays in this browser only. Nothing was saved to the server.',
      )
    } else if (error instanceof ApiAuthError) {
      toast('Session expired — sign in again. Nothing was saved to the server.')
    } else if (error instanceof ApiHttpError) {
      if (error.status === 401) {
        toast('Session or PIN rejected — sign in again. Nothing was saved to the server.')
      } else if (error.status === 409) {
        setConflict(true)
        toast('This shift changed in another session — reload before saving.')
      } else {
        toast(`Save failed (${error.status}): ${error.message}`)
      }
    } else {
      toast('Save failed — no data was written.')
    }
  }

  const onSaveDraft = async () => {
    if (!session) {
      toast('Sign in to save readings to the server.')
      return
    }
    if (!editable) {
      toast('Your role can view shifts but not save readings.')
      return
    }
    if (catalog.length === 0) {
      toast('No active nozzles to save — configure nozzles in Fuel & stock first.')
      return
    }
    setBusy(true)
    try {
      const { saved } = await syncReadings()
      if (saved === 0) {
        toast('No complete nozzle rows to save — enter opening and closing first.')
        return
      }
      const incomplete = catalog.length - saved
      if (incomplete === 0) {
        clearShiftDraft(
          sessionStorage,
          draftScope(shift?.business_date ?? localDate(), shift?.kind ?? shiftKind),
        )
        setDraftRestoredAt(null)
        dirtyRef.current = false
        toast(`Draft saved to the server (${saved} nozzle row${saved === 1 ? '' : 's'}).`)
      } else {
        toast(
          `Saved ${saved} complete nozzle row${saved === 1 ? '' : 's'} to the server. ` +
            `${incomplete} incomplete row${incomplete === 1 ? '' : 's'} kept in this browser only.`,
        )
      }
    } catch (error) {
      handleSaveError(error)
    } finally {
      setBusy(false)
    }
  }

  const onValidate = async () => {
    const found = validateNozzleDraft(rows, rollover, collections)
    setIssues(found)
    setServerIssues([])
    if (found.length > 0) {
      toast(
        `Local validation found ${found.length} issue${found.length === 1 ? '' : 's'} — fix them first.`,
      )
      return
    }
    if (!session) {
      toast('Sign in to validate readings against the server.')
      return
    }
    if (!editable) {
      toast('Your role can view shifts but not validate readings.')
      return
    }
    if (catalog.length === 0) {
      toast('No active nozzles configured for this station.')
      return
    }
    setBusy(true)
    try {
      const { id, saved } = await syncReadings()
      if (saved < catalog.length) {
        toast(
          `Saved ${saved} of ${catalog.length} nozzle rows. Complete every active nozzle before server validation.`,
        )
        return
      }
      const result = await postJson<{ valid: boolean; issues: ServerIssue[] }>(
        `/api/v1/shifts/${id}/validate`,
        { rollover: rolloverPayload },
      )
      setServerIssues(result.issues)
      toast(
        result.valid
          ? 'Server validation passed. Readings are valid for close.'
          : `Server validation found ${result.issues.length} issue${result.issues.length === 1 ? '' : 's'}.`,
      )
    } catch (error) {
      handleSaveError(error)
    } finally {
      setBusy(false)
    }
  }

  const idempotencyKeyFor = (shiftId: string, body: unknown): string => {
    const fingerprint = JSON.stringify(body)
    if (
      idempotencyRef.current &&
      idempotencyRef.current.shiftId === shiftId &&
      idempotencyRef.current.fingerprint === fingerprint
    ) {
      return idempotencyRef.current.key
    }
    const key = crypto.randomUUID()
    idempotencyRef.current = { key, fingerprint, shiftId }
    return key
  }

  const openCloseDialog = () => {
    setIssues(validateNozzleDraft(rows, rollover, collections))
    setConfirmingClose(true)
    setCloseError(null)
    setNeedsOverride(false)
    setNeedsApproval(false)
  }

  const onConfirmClose = async () => {
    if (!session) return
    if (!canClose) {
      toast('Closing a shift requires an owner or manager.')
      return
    }
    setCloseError(null)
    const found = validateNozzleDraft(rows, rollover, collections)
    setIssues(found)
    if (found.length > 0) {
      toast('Fix the highlighted readings before closing.')
      return
    }
    if (catalog.length === 0) {
      toast('No active nozzles configured for this station.')
      return
    }
    if (closingPin.length < 6) {
      toast('Enter your 6+ digit PIN to close this shift.')
      return
    }

    setBusy(true)
    try {
      const { id, saved } = await syncReadings()
      if (saved !== catalog.length) {
        toast(
          `Only ${saved} of ${catalog.length} nozzle rows are complete. Complete every reading before closing.`,
        )
        return
      }

      const body: Record<string, unknown> = {
        rollover: rolloverPayload,
        collections: {
          cash: collections.cash?.trim() || '0',
          upi: collections.upi?.trim() || '0',
          card: collections.card?.trim() || '0',
          other: collections.other?.trim() || '0',
        },
      }
      if (overrideReason.trim()) body.override_reason = overrideReason.trim()

      const headers: Record<string, string> = {
        'Idempotency-Key': idempotencyKeyFor(id, body),
        'X-Reauth-Pin': closingPin,
      }
      if (approvalCode.trim() && approvalPin.trim()) {
        headers['X-Approval-Code'] = approvalCode.trim()
        headers['X-Approval-Pin'] = approvalPin.trim()
      }

      const result = await postJson<{
        status: string
        revenue_total: string
        total_litres: string
        variance: string
        reconciliation_status: string
        idempotent_replay?: boolean
      }>(`/api/v1/shifts/${id}/close`, body, headers)

      idempotencyRef.current = null
      setShift((prev) =>
        prev
          ? {
              ...prev,
              status: result.status,
              closed_at: new Date().toISOString(),
              revenue_total: result.revenue_total,
              variance_amount: result.variance,
              variance_reason: overrideReason.trim() || null,
            }
          : prev,
      )
      setClosedInfo({
        revenue: result.revenue_total,
        litres: result.total_litres,
        variance: result.variance,
        reconciliation: result.reconciliation_status,
      })
      setConfirmingClose(false)
      setClosingPin('')
      setDraftRestoredAt(null)
      dirtyRef.current = false
      clearShiftDraft(
        sessionStorage,
        draftScope(shift?.business_date ?? localDate(), shift?.kind ?? shiftKind),
      )
      toast(
        `Shift closed on the server${result.idempotent_replay ? ' (idempotent replay)' : ''} — revenue ${money(Number(result.revenue_total))}.`,
      )
    } catch (error) {
      if (error instanceof ApiOfflineError) {
        setCloseError(
          'No response from the server. The close may or may not have been recorded. ' +
            'Retry the same close (the app reuses its idempotency key) or check the shift register before posting anything else.',
        )
        toast(
          'Backend did not respond — close status unknown. Retry the same close or check the register.',
        )
      } else if (error instanceof ApiAuthError) {
        setCloseError('Session expired — sign in again. No close was confirmed.')
        toast('Session expired — no close was confirmed.')
      } else if (error instanceof ApiHttpError) {
        const details = (error.details ?? {}) as Record<string, unknown>
        if (error.status === 401) {
          setCloseError(
            'PIN rejected — the close was not accepted. Check your PIN; 5 wrong attempts lock re-authentication for 15 minutes.',
          )
          toast('PIN rejected — close aborted.')
        } else if (error.status === 409) {
          idempotencyRef.current = null
          setConflict(true)
          setCloseError(
            'The server rejected this close because the shift changed or was already closed. Reload before posting anything else.',
          )
          toast('Shift already closed or changed elsewhere — reload to see the current state.')
        } else if (error.status === 422) {
          setNeedsApproval(Boolean(details.approval_required))
          setNeedsOverride(Boolean(details.override_required))
          if (details.approval_required) {
            setCloseError(
              'A second approver is required for a variance over ₹1.00. Enter a different approver code and PIN.',
            )
            toast('Second approver required.')
          } else if (details.override_required) {
            setCloseError(
              `Collections do not reconcile (${String(details.status ?? 'variance')}). ` +
                'Resolve the difference, or enter an override reason and a second approver.',
            )
            toast('Variance requires a reason and a second approver.')
          } else {
            setCloseError(error.message)
            toast(`Server rejected the close: ${error.message}`)
          }
        } else if (error.status === 429) {
          setCloseError(error.message)
          toast(error.message)
        } else {
          setCloseError(error.message)
          toast(`Close failed (${error.status}): ${error.message}`)
        }
      } else {
        setCloseError('Close failed — the server did not confirm the result.')
        toast('Close failed — no confirmation from the server.')
      }
    } finally {
      setBusy(false)
    }
  }

  const issueFor = (field: string) => issues.find((issue) => issue.field === field)?.message

  const renderReadingInput = (row: NozzleReadingInput, part: 'opening' | 'closing') => {
    const field = `${row.nozzleId}:${part}`
    const message = issueFor(field)
    const id = `${row.nozzleId}-${part}`
    const label = `${row.productName} ${row.label} ${part} (L)`
    return (
      <div className="field">
        <label htmlFor={id}>{label}</label>
        <input
          id={id}
          type="number"
          inputMode="decimal"
          value={part === 'opening' ? row.opening : row.closing}
          onChange={onReading(row.nozzleId, part)}
          aria-invalid={message ? true : undefined}
          aria-describedby={message ? `${id}-error` : undefined}
          disabled={isClosed || !editable}
        />
        {message && (
          <div className="field-error" id={`${id}-error`}>
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
          <div className="sub">
            Record opening and closing totalizers for every active nozzle. Selling prices come from
            the server.
          </div>
        </div>
        <div className="actions">
          <button className="btn" onClick={() => window.print()}>
            ⎙ Print
          </button>
        </div>
      </div>

      <div className="notice">
        {catalogMode === 'signed-out' ? (
          <>
            ⓘ <b>Not signed in:</b> sign in to load the station catalog, prices and shifts.
          </>
        ) : catalogMode === 'loading' ? (
          <>ⓘ Loading the station catalog from the server…</>
        ) : catalogMode === 'error' ? (
          <>
            ⓘ <b>Live data unavailable:</b> {catalogError}
          </>
        ) : (
          <>
            ⓘ <b>Live:</b> readings and closes are saved to the server. Prices are configured on the
            server and cannot be typed here.
          </>
        )}
      </div>

      {session && !editable && (
        <div className="notice">
          ⓘ Your role ({session.employee.role}) can view shifts but not edit readings. Saving and
          closing are disabled.
        </div>
      )}

      {conflict && (
        <div
          className="notice"
          style={{ background: '#fff4dd', borderColor: '#f0d9a8', color: '#a96b0c' }}
        >
          This shift changed in another session.{' '}
          <button className="btn" onClick={() => void loadWorkspace()} disabled={busy}>
            Reload from server (keeps your browser draft)
          </button>
        </div>
      )}

      {closedInfo && (
        <div
          className="notice"
          style={{ background: '#e8f8f2', borderColor: '#bfe8d8', color: '#13865f' }}
        >
          ✓ Shift closed on the server. Revenue ₹{' '}
          {Number(closedInfo.revenue).toLocaleString('en-IN')} ·{' '}
          {Number(closedInfo.litres).toLocaleString('en-IN')} L dispensed · variance ₹{' '}
          {Number(closedInfo.variance).toLocaleString('en-IN')} ({closedInfo.reconciliation}).
        </div>
      )}

      {draftRestoredAt && !closedInfo && (
        <div className="notice">
          ⟲ Unsynced draft restored from{' '}
          {new Date(draftRestoredAt).toLocaleTimeString('en-IN', {
            hour: '2-digit',
            minute: '2-digit',
          })}
          . It is kept in this browser and replaces the server draft when you save.
        </div>
      )}

      {catalogMode === 'live' && catalog.length === 0 && (
        <div className="notice">
          ⚠ No active nozzles are configured for this station. Add nozzles in Fuel & stock before
          closing a shift.
        </div>
      )}

      <div className="card">
        <div className="cardhead">
          <h3>
            Shift closing ·{' '}
            {SHIFT_KINDS.find((kind) => kind.value === (shift?.kind ?? shiftKind))?.label ??
              shiftKind}
            {shift?.business_date ? ` · ${shift.business_date}` : ''}
          </h3>
          <span className={isClosed ? 'pill green' : 'pill amber'}>
            {isClosed ? 'Closed' : shift ? 'Draft on server' : 'Not yet saved'}
          </span>
        </div>

        <div className="formgrid">
          <div className="field">
            <label htmlFor="shift-kind">Shift</label>
            <select
              id="shift-kind"
              value={shiftKind}
              onChange={(event) => {
                const value = event.target.value
                if (isShiftKind(value)) {
                  dirtyRef.current = true
                  setShiftKind(value)
                }
              }}
              disabled={Boolean(shift) || isClosed || !editable}
            >
              {SHIFT_KINDS.map((kind) => (
                <option key={kind.value} value={kind.value}>
                  {kind.label}
                </option>
              ))}
            </select>
            {shift && (
              <div className="small">Shift kind is fixed once the draft exists on the server.</div>
            )}
          </div>
          <div className="field">
            <div className="stat-top">Attendant</div>
            <div>
              {session ? `${session.employee.name} (${session.employee.code})` : 'Not signed in'}
            </div>
          </div>
          <div className="field">
            <div className="stat-top">Business date</div>
            <div>{shift?.business_date ?? 'Set by the server when you first save'}</div>
          </div>
        </div>

        {rows.length > 0 && (
          <div className="formgrid" style={{ marginTop: 8 }}>
            {rows.map((row) => (
              <div className="field" key={row.nozzleId}>
                {renderReadingInput(row, 'opening')}
                {renderReadingInput(row, 'closing')}
                {issueFor(`${row.nozzleId}:price`) ? (
                  <div className="field-error" role="alert">
                    {issueFor(`${row.nozzleId}:price`)}
                  </div>
                ) : (
                  <div className="small">
                    {row.unitPrice
                      ? `Server price ₹${row.unitPrice}/L`
                      : 'No selling price configured — set one before closing.'}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        <div className="formgrid" style={{ marginTop: 8 }}>
          {COLLECTION_MODES.map((mode) => {
            const field = `collection:${mode}`
            const message = issueFor(field)
            return (
              <div className="field" key={mode}>
                <label htmlFor={`collection-${mode}`}>{COLLECTION_LABELS[mode]}</label>
                <input
                  id={`collection-${mode}`}
                  type="number"
                  inputMode="decimal"
                  value={collections[mode] ?? ''}
                  onChange={onCollection(mode)}
                  aria-invalid={message ? true : undefined}
                  aria-describedby={message ? `collection-${mode}-error` : undefined}
                  disabled={isClosed || !editable}
                />
                {message && (
                  <div className="field-error" id={`collection-${mode}-error`}>
                    {message}
                  </div>
                )}
              </div>
            )
          })}
        </div>
        <p className="small">
          Credit sales are receivables, not collections — the server excludes them from expected
          cash.
        </p>

        {rolloverProducts.length > 0 && (
          <fieldset className="rollover">
            <legend>Meter rollover / reset (authorized only)</legend>
            <p className="small">
              Authorize only when a totalizer wrapped. The rollover value is the meter wrap value
              (e.g. 100000 for a 5-digit meter) and must be greater than the opening reading.
            </p>
            <div className="formgrid">
              {rolloverProducts.map((product) => {
                const authorization = rollover[product.code]
                return (
                  <div className="field" key={product.code}>
                    <label className="check">
                      <input
                        type="checkbox"
                        checked={authorization?.authorized ?? false}
                        onChange={onRolloverToggle(product.code)}
                        disabled={isClosed || !editable}
                      />
                      {product.name} rollover authorized
                    </label>
                    <input
                      aria-label={`${product.name} rollover value`}
                      type="number"
                      value={authorization?.value ?? '100000'}
                      disabled={!authorization?.authorized || isClosed || !editable}
                      onChange={onRolloverValue(product.code)}
                    />
                  </div>
                )
              })}
            </div>
          </fieldset>
        )}

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

        {confirmingClose && (
          <div className="reauth">
            <label htmlFor="reauth-pin">
              Confirm your PIN to close this shift (re-authentication)
            </label>
            <input
              id="reauth-pin"
              type="password"
              inputMode="numeric"
              minLength={6}
              value={closingPin}
              onChange={(event) => setClosingPin(event.target.value)}
              autoFocus
              autoComplete="current-password"
            />

            {(reconciliation.status !== 'balanced' || needsOverride || needsApproval) && (
              <>
                <div className="field" style={{ marginTop: 12, maxWidth: 420 }}>
                  <label htmlFor="override-reason">
                    Override reason (required when collections do not reconcile)
                  </label>
                  <input
                    id="override-reason"
                    value={overrideReason}
                    onChange={(event) => setOverrideReason(event.target.value)}
                    placeholder="e.g. Manager approved short collection"
                  />
                </div>
                <div className="formgrid">
                  <div className="field">
                    <label htmlFor="approval-code">Second approver code</label>
                    <input
                      id="approval-code"
                      value={approvalCode}
                      onChange={(event) => setApprovalCode(event.target.value)}
                      autoComplete="off"
                    />
                  </div>
                  <div className="field">
                    <label htmlFor="approval-pin">Second approver PIN</label>
                    <input
                      id="approval-pin"
                      type="password"
                      inputMode="numeric"
                      value={approvalPin}
                      onChange={(event) => setApprovalPin(event.target.value)}
                      autoComplete="off"
                    />
                  </div>
                </div>
                <p className="small">
                  A reason and a <b>different</b> owner/manager/accountant are required when the
                  variance exceeds ₹1.00. Self-approval is rejected by the server.
                </p>
              </>
            )}

            {closeError && (
              <div className="field-error" role="alert" style={{ marginTop: 10 }}>
                {closeError}
              </div>
            )}

            <div className="formactions" style={{ marginTop: 10 }}>
              <button
                className="btn primary"
                onClick={() => void onConfirmClose()}
                disabled={busy || closingPin.length < 6}
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
            disabled={busy || isClosed || !editable || catalog.length === 0}
          >
            Save draft
          </button>
          <button
            className="btn"
            onClick={() => void onValidate()}
            disabled={busy || isClosed || catalog.length === 0 || (session !== null && !editable)}
          >
            Validate readings
          </button>
          {!isClosed &&
            (canClose ? (
              <button
                className="btn"
                onClick={openCloseDialog}
                disabled={busy || catalog.length === 0 || !session}
              >
                Close shift
              </button>
            ) : (
              <span className="small">Closing requires an owner or manager.</span>
            ))}
          {isClosed && (
            <button className="btn" onClick={() => window.location.reload()}>
              Start another shift
            </button>
          )}
        </div>
      </div>

      <div className="grid stats" style={{ marginTop: 16 }}>
        {productTotals.map((product) => (
          <div className="card" key={product.code}>
            <div className="stat-top">{product.name}</div>
            <div className="value">{product.volume.toLocaleString('en-IN')} L</div>
            <div className="delta">{money(product.value)}</div>
            <div className="small">{product.nozzles.join(', ')} · volume × server price</div>
          </div>
        ))}
        {productTotals.length === 0 && (
          <div className="card">
            <div className="stat-top">No readings yet</div>
            <div className="small">
              {catalogMode === 'signed-out'
                ? 'Sign in to load the station catalog.'
                : 'Load the catalog or enter nozzle readings to see totals.'}
            </div>
          </div>
        )}
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
                <td>Meter sales (all nozzles)</td>
                <td className="right">{money(totals.totalValue)}</td>
              </tr>
              {creditSalesForShift !== null && (
                <tr>
                  <td>Credit sales on this shift (not collected)</td>
                  <td className="right">− {money(creditSalesForShift)}</td>
                </tr>
              )}
              <tr>
                <td>
                  <b>Expected collections</b>
                </td>
                <td className="right">
                  <b>{money(reconciliation.expected)}</b>
                </td>
              </tr>
              <tr>
                <td>Collections entered</td>
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
        <p className="small" style={{ marginTop: 10 }}>
          The server recomputes this at close and is authoritative. Credit sales are excluded from
          expected collections.
          {creditSalesForShift === null && session
            ? ' Credit-sale details are not visible to this role; the server still excludes them.'
            : ''}
        </p>
      </div>
    </>
  )
}
