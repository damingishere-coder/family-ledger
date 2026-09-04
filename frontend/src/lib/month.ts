const MONTH_PATTERN = /^(\d{4})-(\d{2})$/

export function currentMonthLocal(now = new Date()): string {
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 7)
}

export function snapshotMonth(snapshotDate: string): string {
  return snapshotDate.slice(0, 7)
}

export function monthEndDate(month: string): string {
  const match = MONTH_PATTERN.exec(month)
  if (!match) throw new Error('月份格式必须为 YYYY-MM')
  const year = Number(match[1])
  const monthNumber = Number(match[2])
  if (monthNumber < 1 || monthNumber > 12) throw new Error('月份必须在 01 到 12 之间')
  const day = new Date(Date.UTC(year, monthNumber, 0)).getUTCDate()
  return `${month}-${String(day).padStart(2, '0')}`
}

export function formatSnapshotMonth(snapshotDate: string): string {
  const month = snapshotMonth(snapshotDate)
  const match = MONTH_PATTERN.exec(month)
  if (!match) return snapshotDate
  return `${match[1]}年${match[2]}月`
}

export function formatSnapshotMonthShort(snapshotDate: string): string {
  return formatSnapshotMonth(snapshotDate)
}
