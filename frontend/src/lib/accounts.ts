import type { Account, AccountType, SnapshotEntry } from '../types'

export const ACCOUNT_TYPE_LABELS: Record<AccountType, string> = {
  wallet: '钱包 / 支付平台',
  debit_card: '储蓄卡',
  credit_card: '信用卡',
  investment: '投资账户',
  receivable: '待收欠款',
  other_asset: '其他资产',
  other_liability: '其他负债',
}

export const ACCOUNT_TYPE_OPTIONS = Object.entries(ACCOUNT_TYPE_LABELS) as Array<[AccountType, string]>

export type AccountArchiveFilter = 'active' | 'archived' | 'all'

export interface AccountFilters {
  memberId: string
  accountType: string
  archive: AccountArchiveFilter
  search: string
}

export function filterAccounts(accounts: Account[], filters: AccountFilters) {
  const query = filters.search.trim().toLocaleLowerCase('zh-CN')
  return accounts.filter((account) => {
    if (filters.memberId !== 'all' && String(account.member_id) !== filters.memberId) return false
    if (filters.accountType !== 'all' && account.account_type !== filters.accountType) return false
    if (filters.archive === 'active' && account.is_archived) return false
    if (filters.archive === 'archived' && !account.is_archived) return false
    if (!query) return true
    return [account.member_name, account.name, account.institution, account.notes]
      .filter(Boolean)
      .some((value) => String(value).toLocaleLowerCase('zh-CN').includes(query))
  })
}

export function groupEntries(entries: SnapshotEntry[]) {
  const groups: Record<string, Record<string, SnapshotEntry[]>> = {}
  for (const entry of entries) {
    groups[entry.member_name] ??= {}
    groups[entry.member_name][entry.account_type] ??= []
    groups[entry.member_name][entry.account_type].push(entry)
  }
  return groups
}
