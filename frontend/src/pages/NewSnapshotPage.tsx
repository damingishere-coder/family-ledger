import { AlertTriangle, Check, Keyboard, Save, Sparkles } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import EmptyState from '../components/EmptyState'
import LoadingState from '../components/LoadingState'
import { ACCOUNT_TYPE_LABELS, groupEntries } from '../lib/accounts'
import { api, ApiError, errorMessage } from '../lib/api'
import { currentMonthLocal, formatSnapshotMonth, monthEndDate, snapshotMonth } from '../lib/month'
import { calculateEntries, formatMoney, parseAmountToCents } from '../lib/money'
import { useAmountEditor, useSaveBeforeLeave } from '../lib/useAmountEditor'
import type { Account, Snapshot } from '../types'

interface MonthConflict {
  code: 'SNAPSHOT_MONTH_EXISTS'
  message: string
  snapshot_id: number
  snapshot_month: string
}

function monthConflict(reason: unknown): MonthConflict | null {
  if (!(reason instanceof ApiError) || reason.status !== 409 || typeof reason.detail !== 'object' || reason.detail === null) return null
  const detail = reason.detail as Partial<MonthConflict>
  if (detail.code !== 'SNAPSHOT_MONTH_EXISTS' || !detail.snapshot_id || !detail.snapshot_month) return null
  return detail as MonthConflict
}

const assetInputTypes = ['wallet', 'debit_card', 'investment', 'receivable', 'other_asset'] as const
const liabilityInputTypes = ['credit_card', 'other_liability'] as const

export default function NewSnapshotPage() {
  const { snapshot, values, error, setError, saving, saveStatus, initialize: initializeValues,
    changeValue, saveAll, dirty } = useAmountEditor()
  const leaving = useSaveBeforeLeave(dirty, saveAll)
  const [accountsReady, setAccountsReady] = useState<boolean | null>(null)
  const [selectedMonth, setSelectedMonth] = useState(currentMonthLocal())
  const [draftInfo, setDraftInfo] = useState<Snapshot | null>(null)
  const [working, setWorking] = useState(false)
  const [existingMonth, setExistingMonth] = useState<MonthConflict | null>(null)
  const inputRefs = useRef<Array<HTMLInputElement | null>>([])
  const navigate = useNavigate()
  const busy = working || leaving
  useEffect(() => {
    let active = true
    Promise.all([api.get<Account[]>('/accounts?include_archived=false'), api.get<Snapshot | null>('/snapshots/active-draft')])
      .then(([accounts, draft]) => {
        if (!active) return
        setAccountsReady(accounts.length > 0); setDraftInfo(draft)
        if (draft) setSelectedMonth(snapshotMonth(draft.snapshot_date))
      }).catch(reason => { if (active) setError(errorMessage(reason)) })
    return () => { active = false }
  }, [setError])
  const begin = async () => {
    setWorking(true); setError(''); setExistingMonth(null)
    try {
      const data = await api.post<Snapshot>('/snapshots', { snapshot_date: monthEndDate(selectedMonth) })
      initializeValues(data); setSelectedMonth(snapshotMonth(data.snapshot_date))
    } catch (reason) {
      const conflict = monthConflict(reason)
      if (conflict) setExistingMonth(conflict)
      else setError(errorMessage(reason))
    } finally { setWorking(false) }
  }
  const complete = async () => {
    if (!snapshot || busy) return
    setWorking(true)
    if (!(await saveAll())) { setWorking(false); return }
    try {
      const completed = await api.post<Snapshot>(`/snapshots/${snapshot.id}/complete`, { allow_incomplete: false })
      navigate(`/snapshots/${completed.id}`)
    } catch (reason) {
      const conflict = monthConflict(reason)
      if (conflict) {
        setExistingMonth(conflict)
        return
      }
      if (reason instanceof ApiError && reason.status === 409 && typeof reason.detail === 'object' && reason.detail !== null) {
        const detail = reason.detail as { code?: string; message?: string; entries?: Array<{ account_name: string }> }
        if (detail.code !== 'INCOMPLETE_ENTRIES') {
          setError(errorMessage(reason))
          return
        }
        const names = (detail.entries ?? []).map((entry) => entry.account_name).join('、')
        const confirmed = window.confirm(`${detail.message ?? '仍有账户未填写'}：\n${names}\n\n确认将这些空白保留为“未填写”并完成盘点吗？`)
        if (confirmed) {
          const completed = await api.post<Snapshot>(`/snapshots/${snapshot.id}/complete`, { allow_incomplete: true })
          navigate(`/snapshots/${completed.id}`)
        }
      } else {
        setError(errorMessage(reason))
      }
    } finally { setWorking(false) }
  }

  const updateMonth = async (month: string) => {
    if (!month) return
    setError('')
    setExistingMonth(null)
    if (!snapshot) { setSelectedMonth(month); return }
    setWorking(true)
    if (!(await saveAll())) { setWorking(false); return }
    const previousMonth = snapshotMonth(snapshot.snapshot_date)
    try {
      initializeValues(await api.patch<Snapshot>(`/snapshots/${snapshot.id}`, { snapshot_date: monthEndDate(month) }))
      setSelectedMonth(month)
    } catch (reason) {
      setSelectedMonth(previousMonth)
      const conflict = monthConflict(reason)
      if (conflict) setExistingMonth(conflict)
      else setError(errorMessage(reason))
    } finally { setWorking(false) }
  }

  const totals = useMemo(() => calculateEntries(snapshot?.entries ?? [], values), [snapshot?.entries, values])
  const groups = useMemo(() => groupEntries(snapshot?.entries ?? []), [snapshot?.entries])

  const navigateInput = (currentIndex: number, delta: number) => {
    const target = inputRefs.current[currentIndex + delta]
    if (target) {
      target.focus()
      target.select()
    }
  }

  if (error && accountsReady === null) return <div className="page"><div className="notice error">{error}</div></div>
  if (accountsReady === null) return <LoadingState label="正在准备本期盘点…" />
  if (!accountsReady) return <div className="page"><header className="page-header compact-page-header"><div><h1>月度盘点</h1><p>快速录入本期账户余额</p></div></header><EmptyState title="先创建家庭成员和账户" description="盘点会自动复制全部未归档账户，但不会把上一期金额填入本期。" action={<Link className="button primary" to="/accounts">前往账户管理</Link>} /></div>
  if (!snapshot) return <div className="page"><header className="page-header"><div><h1>月度盘点</h1><p>先选择月份，再填写每个账户的当前余额。</p></div></header><>{error && <div className="notice error">{error}</div>}<section className="panel month-start"><h2>{draftInfo ? '有一份未完成的盘点' : '开始一次家庭资产盘点'}</h2><p>{draftInfo ? `${formatSnapshotMonth(draftInfo.snapshot_date)}的输入已保存，继续即可接着填写。` : '上期余额会显示在旁边供参考，本期金额保持空白。'}</p><label>盘点月份<input type="month" aria-label="盘点月份" value={selectedMonth} disabled={!!draftInfo || working} onChange={e => { setSelectedMonth(e.target.value); setExistingMonth(null) }} /></label><button className="button primary" disabled={working || !selectedMonth} onClick={() => void begin()}>{working ? '正在准备…' : draftInfo ? '继续草稿' : '开始填写'}</button>{existingMonth && <div className="notice warning">该月已有完成记录。<Link className="text-link" to={`/snapshots/${existingMonth.snapshot_id}`}>查看本月盘点</Link></div>}</section></></div>

  let inputIndex = -1
  return (
    <div className="page snapshot-page">
      <header className="page-header snapshot-header">
        <div className="snapshot-header-main">
          <div><h1>月度盘点</h1><p><Keyboard size={14} /> Enter / ↓ 下一项，↑ 上一项，Tab 正常切换</p></div>
          <div className="snapshot-actions"><label>盘点月份<input type="month" value={selectedMonth} disabled={busy} onChange={(event) => updateMonth(event.target.value)} /></label><button className="button secondary" disabled={busy || saving} onClick={() => void saveAll()}><Save size={16} /> 保存草稿</button><button className="button primary" disabled={busy} onClick={() => void complete()}><Sparkles size={16} /> 完成盘点</button></div>
        </div>
        <div className="snapshot-progress">
          <div className="progress-track"><span style={{ width: `${totals.total_entries ? totals.completed_entries / totals.total_entries * 100 : 0}%` }} /></div>
          <span className="progress-text">已完成 {totals.completed_entries} / {totals.total_entries} 个账户</span>
          <span className={`save-state ${saveStatus.includes('失败') || saveStatus.includes('尚未') ? 'has-error' : ''}`}><span className="status-dot" /> {saveStatus}</span>
        </div>
      </header>
      {existingMonth && <div className="notice warning">{existingMonth.message}。<Link className="text-link" to={`/snapshots/${existingMonth.snapshot_id}`}>查看本月盘点</Link></div>}
      {error && <div className="notice error">{error}</div>}

      {Object.entries(groups).map(([memberName, typeGroups]) => (
        <section className="panel snapshot-member" key={memberName}>
          <div className="member-section-header"><div className="member-avatar">{memberName.slice(0, 1)}</div><div><h2>{memberName}</h2><p>{Object.values(typeGroups).flat().length} 个账户</p></div></div>
          <div className="member-entry-columns">
            {[
              { key: 'assets', label: '资产与待收款', types: assetInputTypes },
              { key: 'liabilities', label: '信用卡与负债账户', types: liabilityInputTypes },
            ].map((column) => {
              const columnEntries = column.types.flatMap((type) => typeGroups[type] ?? [])
              return (
                <div className="entry-column" key={column.key}>
                  <div className="entry-column-title"><h3>{column.label}</h3><span>{columnEntries.length} 项</span></div>
                  <div className="entry-row entry-head"><span>账户</span><span>上期余额</span><span>本期余额</span><span>变化</span></div>
                  {columnEntries.length ? columnEntries.map((entry) => {
                    inputIndex += 1
                    const currentIndex = inputIndex
                    let currentCents: number | null = null
                    try { currentCents = parseAmountToCents(values[entry.id] ?? '') } catch { /* field shows the validation error */ }
                    const change = currentCents !== null && entry.previous_amount_cents !== null ? currentCents - entry.previous_amount_cents : null
                    const largeChange = change !== null && Math.abs(change) >= 100_000 && Math.abs(change) >= Math.max(Math.abs(entry.previous_amount_cents ?? 0), 10_000) * 5
                    return <div className="entry-row" key={entry.id}><div className="account-cell"><strong>{entry.account_name}</strong><small>{entry.institution || ACCOUNT_TYPE_LABELS[entry.account_type]}{!entry.include_in_net_worth ? ' · 不计入' : ''}</small></div><span className="previous-value">{formatMoney(entry.previous_amount_cents)}</span><div className="input-cell"><span>¥</span><input ref={(element) => { inputRefs.current[currentIndex] = element }} className="money-input" disabled={busy} aria-label={`${memberName} ${entry.account_name} 本期余额`} inputMode="decimal" placeholder="请输入" value={values[entry.id] ?? ''} onChange={(event) => changeValue(entry.id, event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === 'ArrowDown') { event.preventDefault(); navigateInput(currentIndex, 1) } else if (event.key === 'ArrowUp') { event.preventDefault(); navigateInput(currentIndex, -1) } }} /></div><span className={change !== null && (column.key === 'liabilities' ? change > 0 : change < 0) ? 'negative' : 'positive'}>{formatMoney(change, true)}{largeChange && <span className="change-warning" title="较上期变化较大，请确认金额"><AlertTriangle size={13} /></span>}</span></div>
                  }) : <div className="inline-empty compact-empty">暂无账户</div>}
                </div>
              )
            })}
          </div>
        </section>
      ))}
      <div className="snapshot-summary"><div><span>本期资产</span><strong>{formatMoney(totals.total_assets_cents)}</strong></div><div className="liability-total"><span>本期负债</span><strong>{formatMoney(totals.total_liabilities_cents)}</strong></div><div className="featured"><span>家庭净资产</span><strong>{formatMoney(totals.net_worth_cents)}</strong></div><div className="summary-confirm"><Check size={16} /> 自动计算</div></div>
    </div>
  )
}
