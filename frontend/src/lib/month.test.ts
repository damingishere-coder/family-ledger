import { describe, expect, it } from 'vitest'
import {
  currentMonthLocal,
  formatSnapshotMonth,
  formatSnapshotMonthShort,
  monthEndDate,
  snapshotMonth,
} from './month'

describe('month helpers', () => {
  it('converts a month to its final calendar day', () => {
    expect(monthEndDate('2026-02')).toBe('2026-02-28')
    expect(monthEndDate('2024-02')).toBe('2024-02-29')
    expect(monthEndDate('2026-09')).toBe('2026-09-30')
  })

  it('formats stored dates as months', () => {
    expect(snapshotMonth('2026-08-31')).toBe('2026-08')
    expect(formatSnapshotMonth('2026-08-31')).toBe('2026年08月')
    expect(formatSnapshotMonthShort('2026-08-31')).toBe('2026年08月')
  })

  it('uses local calendar time instead of UTC for the default month', () => {
    const nearMidnight = new Date('2026-08-31T16:30:00.000Z')
    const original = nearMidnight.getTimezoneOffset
    nearMidnight.getTimezoneOffset = () => -480
    expect(currentMonthLocal(nearMidnight)).toBe('2026-09')
    nearMidnight.getTimezoneOffset = original
  })

  it('rejects invalid month values', () => {
    expect(() => monthEndDate('2026-13')).toThrow('月份必须在 01 到 12 之间')
    expect(() => monthEndDate('2026-1')).toThrow('月份格式必须为 YYYY-MM')
  })
})
