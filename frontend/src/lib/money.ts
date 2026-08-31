import type { SnapshotEntry, Totals } from '../types'

const MONEY_PATTERN = /^[-+]?(?:\d+)(?:\.\d{0,2})?$/

export function parseAmountToCents(raw: string): number | null {
  const value = raw.trim().replaceAll(',', '').replace(/[¥￥元\s]/g, '')
  if (value === '') return null
  if (!MONEY_PATTERN.test(value)) {
    throw new Error('请输入最多两位小数的金额')
  }
  const negative = value.startsWith('-')
  const unsigned = value.replace(/^[-+]/, '')
  const [integerPart, decimalPart = ''] = unsigned.split('.')
  const cents = Number(integerPart) * 100 + Number(decimalPart.padEnd(2, '0'))
  if (!Number.isSafeInteger(cents)) {
    throw new Error('金额超出安全范围')
  }
  return negative ? -cents : cents
}

export function centsToInput(cents: number | null): string {
  if (cents === null) return ''
  const negative = cents < 0 ? '-' : ''
  const absolute = Math.abs(cents)
  return `${negative}${Math.floor(absolute / 100)}.${String(absolute % 100).padStart(2, '0')}`
}

export function formatMoney(cents: number | null | undefined, showSign = false): string {
  if (cents === null || cents === undefined) return '—'
  const amount = new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
    minimumFractionDigits: 2,
  }).format(Math.abs(cents) / 100)
  if (cents < 0) return `-${amount}`
  return showSign && cents > 0 ? `+${amount}` : amount
}

const ASSET_TYPES = new Set(['wallet', 'debit_card', 'investment', 'receivable', 'other_asset'])

export function calculateEntries(
  entries: SnapshotEntry[],
  values: Record<number, string>,
): Totals {
  let assets = 0
  let liabilities = 0
  let investments = 0
  let completed = 0
  for (const entry of entries) {
    let amount: number | null
    try {
      amount = parseAmountToCents(values[entry.id] ?? '')
    } catch {
      continue
    }
    if (amount === null) continue
    completed += 1
    if (!entry.include_in_net_worth) continue
    if (ASSET_TYPES.has(entry.account_type)) {
      assets += amount
      if (entry.account_type === 'investment') investments += amount
    } else {
      liabilities += amount
    }
  }
  return {
    total_assets_cents: assets,
    total_liabilities_cents: liabilities,
    net_worth_cents: assets - liabilities,
    investment_assets_cents: investments,
    completed_entries: completed,
    total_entries: entries.length,
  }
}
