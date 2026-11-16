/**
 * Illustrative sample data ported from the single-file prototype.
 * Everything here is demo-only; no real transactions exist yet.
 */

export const recentTransactions = [
  {
    time: '18:02',
    label: 'Diesel · Nozzle D1',
    mode: 'UPI',
    amount: '₹ 2,500',
    status: 'Recorded',
    tone: 'green',
  },
  {
    time: '17:48',
    label: 'Petrol · Nozzle P2',
    mode: 'Cash',
    amount: '₹ 1,200',
    status: 'Recorded',
    tone: 'green',
  },
  {
    time: '17:31',
    label: 'Fleet customer · AC-014',
    mode: 'Credit',
    amount: '₹ 4,800',
    status: 'On account',
    tone: 'amber',
  },
  {
    time: '17:12',
    label: 'Petrol · Nozzle P1',
    mode: 'Card',
    amount: '₹ 900',
    status: 'Recorded',
    tone: 'green',
  },
] as const

export const shiftStatus = [
  { name: 'Morning shift', meta: '06:00 – 14:00 · Ravi', status: 'Closed', tone: 'green' },
  { name: 'Afternoon shift', meta: '14:00 – 22:00 · Kumar', status: 'In progress', tone: 'amber' },
  { name: 'Night shift', meta: '22:00 – 06:00 · —', status: 'Upcoming', tone: 'blue' },
] as const

export const salesTrend = [
  { day: '09', height: 55 },
  { day: '10', height: 68 },
  { day: '11', height: 49 },
  { day: '12', height: 78 },
  { day: '13', height: 62 },
  { day: '14', height: 86 },
  { day: '15', height: 72, today: true },
] as const

export const tankRegister = [
  {
    tank: 'T-01',
    product: 'Petrol',
    capacity: '15,000 L',
    book: '8,420 L',
    dip: '8,402 L',
    variance: '−18 L',
    tone: 'amber',
    level: '56%',
  },
  {
    tank: 'T-02',
    product: 'Diesel',
    capacity: '20,000 L',
    book: '11,280 L',
    dip: '11,295 L',
    variance: '+15 L',
    tone: 'green',
    level: '56%',
  },
] as const

export const fuelReceipts = [
  {
    date: '14 Nov 2026',
    supplier: 'Oil Company Depot',
    product: 'Petrol',
    qty: '6,000 L',
    invoice: 'INV-24091',
    status: 'Posted',
    tone: 'green',
  },
  {
    date: '13 Nov 2026',
    supplier: 'Oil Company Depot',
    product: 'Diesel',
    qty: '8,000 L',
    invoice: 'INV-24072',
    status: 'Posted',
    tone: 'green',
  },
] as const

export const creditAccounts = [
  {
    customer: 'Sri Lakshmi Transport',
    account: 'AC-014',
    limit: '₹ 50,000',
    outstanding: '₹ 24,800',
    last: 'Today · ₹4,800',
    status: 'Near limit',
    tone: 'amber',
  },
  {
    customer: 'Melkote Agro Services',
    account: 'AC-006',
    limit: '₹ 75,000',
    outstanding: '₹ 18,200',
    last: 'Today · ₹2,400',
    status: 'Active',
    tone: 'green',
  },
  {
    customer: 'Ravi Enterprises',
    account: 'AC-021',
    limit: '₹ 25,000',
    outstanding: '₹ 28,400',
    last: '08 Nov · ₹1,600',
    status: 'Over limit',
    tone: 'red',
  },
  {
    customer: 'Green Field Farms',
    account: 'AC-009',
    limit: '₹ 40,000',
    outstanding: '₹ 12,600',
    last: 'Yesterday · ₹3,100',
    status: 'Active',
    tone: 'green',
  },
] as const

export const dailySales = [
  { product: 'Petrol', volume: '1,624 L', value: '₹ 1,66,460' },
  { product: 'Diesel', volume: '2,219 L', value: '₹ 1,98,600' },
  { product: 'Lubricants', volume: '—', value: '₹ 19,590' },
  { product: 'Total', volume: '3,842.6 L', value: '₹ 2,84,650', total: true },
] as const

export const collectionBreakdown = [
  { mode: 'Cash', amount: '₹ 96,420', share: '33.9%', tone: 'green' },
  { mode: 'UPI', amount: '₹ 1,12,600', share: '39.5%', tone: 'blue' },
  { mode: 'Card', amount: '₹ 57,180', share: '20.1%', tone: 'blue' },
  { mode: 'Credit', amount: '₹ 18,450', share: '6.5%', tone: 'amber' },
] as const

export const reportCatalogue = [
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
