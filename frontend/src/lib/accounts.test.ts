import { describe, expect, it } from 'vitest'
import { filterAccounts } from './accounts'
import type { Account } from '../types'

const account = (overrides: Partial<Account>): Account => ({
  id: 1,
  member_id: 1,
  member_name: '大明',
  name: '招商银行信用卡',
  institution: '招商银行',
  account_type: 'credit_card',
  credit_limit_cents: 8_000_000,
  billing_day: 11,
  include_in_net_worth: true,
  is_archived: false,
  sort_order: 0,
  notes: null,
  ...overrides,
})

describe('account filters', () => {
  const accounts = [
    account({ id: 1 }),
    account({ id: 2, member_id: 2, member_name: '贤贤', name: '支付宝', institution: null, account_type: 'wallet' }),
    account({ id: 3, name: '旧储蓄卡', institution: '建设银行', account_type: 'debit_card', is_archived: true }),
  ]

  it('combines member, type and archive filters', () => {
    expect(filterAccounts(accounts, { memberId: '1', accountType: 'credit_card', archive: 'active', search: '' }).map((item) => item.id)).toEqual([1])
    expect(filterAccounts(accounts, { memberId: 'all', accountType: 'all', archive: 'archived', search: '' }).map((item) => item.id)).toEqual([3])
  })

  it('searches member, account and institution names', () => {
    expect(filterAccounts(accounts, { memberId: 'all', accountType: 'all', archive: 'all', search: '贤贤' }).map((item) => item.id)).toEqual([2])
    expect(filterAccounts(accounts, { memberId: 'all', accountType: 'all', archive: 'all', search: '招商' }).map((item) => item.id)).toEqual([1])
  })
})
