export function money(n: number): string {
  return '₹ ' + Number(n).toLocaleString('en-IN', { maximumFractionDigits: 2 })
}
