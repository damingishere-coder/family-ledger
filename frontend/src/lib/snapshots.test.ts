import { describe, expect, it } from 'vitest'
import { compareSnapshots } from './snapshots'
import type { Snapshot } from '../types'

const snapshot = (overrides: Partial<Snapshot>): Snapshot => ({
  id: 1,
  snapshot_date: '2026-08-31',
  title: null,
  status: 'completed',
  notes: null,
  legacy_source: null,
  previous_snapshot_id: null,
  total_assets_cents: 100_000,
  total_liabilities_cents: 20_000,
  net_worth_cents: 80_000,
  investment_assets_cents: 0,
  completed_entries: 2,
  total_entries: 2,
  ...overrides,
})

describe('snapshot comparison', () => {
  it('calculates period changes with integer cents', () => {
    expect(compareSnapshots(snapshot({}), snapshot({ total_assets_cents: 90_000, total_liabilities_cents: 25_000, net_worth_cents: 65_000 }))).toEqual({
      assets_cents: 10_000,
      liabilities_cents: -5_000,
      net_worth_cents: 15_000,
    })
  })

  it('returns null changes without a previous snapshot', () => {
    expect(compareSnapshots(snapshot({}), undefined)).toEqual({ assets_cents: null, liabilities_cents: null, net_worth_cents: null })
  })
})
