import { describe, expect, it } from 'vitest'
import { calculateEntries, centsToInput, parseAmountToCents } from './money'
import type { SnapshotEntry } from '../types'

function entry(overrides: Partial<SnapshotEntry>): SnapshotEntry {
  return {
    id: 1,
    snapshot_id: 1,
    account_id: 1,
    member_name: '大明',
    account_name: '账户',
    institution: null,
    account_type: 'wallet',
    amount_cents: null,
    previous_amount_cents: null,
    change_cents: null,
    large_change_warning: false,
    credit_limit_cents: null,
    include_in_net_worth: true,
    notes: null,
    legacy_raw_name: null,
    legacy_raw_value: null,
    ...overrides,
  }
}

describe('money parsing', () => {
  it('parses integer, decimal, negative and blank without floating arithmetic', () => {
    expect(parseAmountToCents('12')).toBe(1200)
    expect(parseAmountToCents('12.35')).toBe(1235)
    expect(parseAmountToCents('-18.52')).toBe(-1852)
    expect(parseAmountToCents('')).toBeNull()
    expect(centsToInput(-1852)).toBe('-18.52')
  })

  it('rejects more than two decimal places', () => {
    expect(() => parseAmountToCents('1.234')).toThrow(/两位小数/)
  })
})

describe('live totals', () => {
  it('distinguishes assets, liabilities, excluded entries and null', () => {
    const entries = [
      entry({ id: 1, account_type: 'wallet' }),
      entry({ id: 2, account_type: 'credit_card' }),
      entry({ id: 3, account_type: 'receivable', include_in_net_worth: false }),
      entry({ id: 4, account_type: 'investment' }),
    ]
    const totals = calculateEntries(entries, { 1: '100', 2: '-18.52', 3: '1000', 4: '' })
    expect(totals.total_assets_cents).toBe(10_000)
    expect(totals.total_liabilities_cents).toBe(-1_852)
    expect(totals.net_worth_cents).toBe(11_852)
    expect(totals.completed_entries).toBe(3)
    expect(totals.total_entries).toBe(4)
  })
})
