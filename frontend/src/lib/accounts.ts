import type { AccountType, SnapshotEntry } from '../types'

export const ACCOUNT_TYPE_LABELS: Record<AccountType, string> = {
  wallet: '钱包 / 支付平台',
  debit_card: '储蓄卡',
  credit_card: '信用卡',
  investment: '投资账户',
  receivable: '应收款',
  other_asset: '其他资产',
  other_liability: '其他负债',
}

export const ACCOUNT_TYPE_OPTIONS = Object.entries(ACCOUNT_TYPE_LABELS) as Array<[AccountType, string]>

export function groupEntries(entries: SnapshotEntry[]) {
  const groups: Record<string, Record<string, SnapshotEntry[]>> = {}
  for (const entry of entries) {
    groups[entry.member_name] ??= {}
    groups[entry.member_name][entry.account_type] ??= []
    groups[entry.member_name][entry.account_type].push(entry)
  }
  return groups
}
