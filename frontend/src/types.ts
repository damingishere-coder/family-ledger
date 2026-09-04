export type AccountType =
  | 'wallet'
  | 'debit_card'
  | 'credit_card'
  | 'investment'
  | 'receivable'
  | 'other_asset'
  | 'other_liability'

export interface Member {
  id: number
  name: string
  display_name: string | null
  sort_order: number
  is_active: boolean
}

export interface Account {
  id: number
  member_id: number
  member_name: string
  name: string
  institution: string | null
  account_type: AccountType
  credit_limit_cents: number | null
  billing_day: number | null
  include_in_net_worth: boolean
  is_archived: boolean
  sort_order: number
  notes: string | null
}

export interface Totals {
  total_assets_cents: number
  total_liabilities_cents: number
  net_worth_cents: number
  investment_assets_cents: number
  completed_entries: number
  total_entries: number
}

export interface SnapshotEntry {
  id: number
  snapshot_id: number
  account_id: number
  member_name: string
  account_name: string
  institution: string | null
  account_type: AccountType
  amount_cents: number | null
  previous_amount_cents: number | null
  change_cents: number | null
  large_change_warning: boolean
  credit_limit_cents: number | null
  include_in_net_worth: boolean
  notes: string | null
  legacy_raw_name: string | null
  legacy_raw_value: string | null
}

export interface Snapshot extends Totals {
  id: number
  snapshot_date: string
  title: string | null
  status: 'draft' | 'completed'
  notes: string | null
  legacy_source: string | null
  previous_snapshot_id: number | null
  entries?: SnapshotEntry[]
}

export interface DashboardData {
  current: Totals | null
  snapshot_id?: number
  snapshot_date?: string
  change_from_previous_cents: number | null
  trend: Array<{
    id: number
    date: string
    total_assets_cents: number
    total_liabilities_cents: number
    net_worth_cents: number
  }>
  composition: Array<{ name: string; amount_cents: number }>
  members: Array<{
    name: string
    assets_cents: number
    liabilities_cents: number
    net_worth_cents: number
  }>
  recent: Snapshot[]
}

export interface ImportRecord {
  id: number
  source_filename: string
  source_type: string
  imported_at: string
  status: string
  total_rows: number
  success_rows: number
  warning_rows: number
  error_rows: number
  report: {
    warnings?: string[]
    errors?: string[]
  }
}

export interface ImportPreviewSnapshot {
  snapshot_date: string | null
  source_date: string | null
  row_count: number
  will_skip: boolean
  layout: string
  source_sheet: string | null
  status: 'importable' | 'duplicate' | 'blocked' | 'ignored'
  blocking_errors: string[]
  source_summary: Record<string, number | null>
  calculated_summary: Totals
  differences: Array<{
    field: string
    source_cents: number
    calculated_cents: number
    residual_cents: number
    explained: boolean
    reason: string | null
  }>
  warnings: string[]
}

export interface ImportPreview {
  source_filename: string
  source_type: 'markdown' | 'csv' | 'xlsx'
  detected_encoding: string | null
  total_snapshots: number
  total_rows: number
  importable_rows: number
  duplicate_snapshots: number
  blocked_snapshots: number
  ignored_snapshots: number
  warning_rows: number
  warnings: string[]
  snapshots: ImportPreviewSnapshot[]
}
