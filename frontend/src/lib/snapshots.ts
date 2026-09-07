import type { Snapshot } from '../types'

export interface SnapshotComparison {
  assets_cents: number | null
  liabilities_cents: number | null
  net_worth_cents: number | null
}

export function compareSnapshots(
  current: Snapshot | undefined,
  previous: Snapshot | undefined,
): SnapshotComparison {
  if (!current || !previous) {
    return { assets_cents: null, liabilities_cents: null, net_worth_cents: null }
  }
  return {
    assets_cents: current.total_assets_cents - previous.total_assets_cents,
    liabilities_cents: current.total_liabilities_cents - previous.total_liabilities_cents,
    net_worth_cents: current.net_worth_cents - previous.net_worth_cents,
  }
}
