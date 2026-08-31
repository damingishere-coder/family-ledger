import { AlertTriangle, Check, Keyboard, Save, Sparkles } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import EmptyState from '../components/EmptyState'
import LoadingState from '../components/LoadingState'
import { ACCOUNT_TYPE_LABELS, groupEntries } from '../lib/accounts'
import { api, ApiError, errorMessage } from '../lib/api'
import { calculateEntries, centsToInput, formatMoney, parseAmountToCents } from '../lib/money'
import type { Account, Snapshot } from '../types'

function todayLocal() {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}

export default function NewSnapshotPage() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [accountsReady, setAccountsReady] = useState<boolean | null>(null)
  const [values, setValues] = useState<Record<number, string>>({})
  const [fieldErrors, setFieldErrors] = useState<Record<number, string>>({})
  const [saveStatus, setSaveStatus] = useState('准备中…')
  const [error, setError] = useState('')
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>())
  const inputRefs = useRef<Array<HTMLInputElement | null>>([])
  const navigate = useNavigate()

  const initializeValues = useCallback((data: Snapshot) => {
    setSnapshot(data)
    setValues(Object.fromEntries((data.entries ?? []).map((entry) => [entry.id, centsToInput(entry.amount_cents)])))
    setSaveStatus('草稿已就绪')
  }, [])

  useEffect(() => {
    let active = true
    api.get<Account[]>('/accounts?include_archived=false').then(async (accounts) => {
      if (!active) return
      setAccountsReady(accounts.length > 0)
      if (!accounts.length) return
      const draft = await api.get<Snapshot | null>('/snapshots/active-draft')
      const data = draft ?? await api.post<Snapshot>('/snapshots', { snapshot_date: todayLocal() })
      if (active) initializeValues(data)
    }).catch((reason) => active && setError(errorMessage(reason)))
    return () => {
      active = false
      timers.current.forEach(clearTimeout)
    }
  }, [initializeValues])

  const persistEntry = useCallback(async (entryId: number, raw: string) => {
    if (!snapshot) return
    try {
      const amount = parseAmountToCents(raw)
      setFieldErrors((current) => { const next = { ...current }; delete next[entryId]; return next })
      setSaveStatus('正在自动保存…')
      const updated = await api.put<Snapshot>(`/snapshots/${snapshot.id}/entries/${entryId}`, { amount_cents: amount })
      setSnapshot(updated)
      setSaveStatus(`已自动保存 ${new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`)
    } catch (reason) {
      setFieldErrors((current) => ({ ...current, [entryId]: errorMessage(reason) }))
      setSaveStatus('有内容尚未保存')
    }
  }, [snapshot])

  const changeValue = (entryId: number, raw: string) => {
    setValues((current) => ({ ...current, [entryId]: raw }))
    setSaveStatus('等待自动保存…')
    const existing = timers.current.get(entryId)
    if (existing) clearTimeout(existing)
    timers.current.set(entryId, setTimeout(() => persistEntry(entryId, raw), 550))
  }

  const saveAll = async () => {
    if (!snapshot) return false
    timers.current.forEach(clearTimeout)
    timers.current.clear()
    setSaveStatus('正在保存全部内容…')
    try {
      for (const entry of snapshot.entries ?? []) {
        const amount = parseAmountToCents(values[entry.id] ?? '')
        if (amount !== entry.amount_cents) {
          const updated = await api.put<Snapshot>(`/snapshots/${snapshot.id}/entries/${entry.id}`, { amount_cents: amount })
          setSnapshot(updated)
        }
      }
      setFieldErrors({})
      setSaveStatus('草稿已保存')
      return true
    } catch (reason) {
      setError(errorMessage(reason))
      setSaveStatus('保存失败')
      return false
    }
  }

  const complete = async () => {
    if (!snapshot || !(await saveAll())) return
    try {
      const completed = await api.post<Snapshot>(`/snapshots/${snapshot.id}/complete`, { allow_incomplete: false })
      navigate(`/snapshots/${completed.id}`)
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 409 && typeof reason.detail === 'object' && reason.detail !== null) {
        const detail = reason.detail as { message?: string; entries?: Array<{ account_name: string }> }
        const names = (detail.entries ?? []).map((entry) => entry.account_name).join('、')
        const confirmed = window.confirm(`${detail.message ?? '仍有账户未填写'}：\n${names}\n\n确认将这些空白保留为“未填写”并完成盘点吗？`)
        if (confirmed) {
          const completed = await api.post<Snapshot>(`/snapshots/${snapshot.id}/complete`, { allow_incomplete: true })
          navigate(`/snapshots/${completed.id}`)
        }
      } else {
        setError(errorMessage(reason))
      }
    }
  }

  const updateDate = async (date: string) => {
    if (!snapshot) return
    setSnapshot(await api.patch<Snapshot>(`/snapshots/${snapshot.id}`, { snapshot_date: date }))
  }

  const totals = useMemo(() => calculateEntries(snapshot?.entries ?? [], values), [snapshot?.entries, values])
  const groups = useMemo(() => groupEntries(snapshot?.entries ?? []), [snapshot?.entries])
  const orderedEntries = snapshot?.entries ?? []

  const navigateInput = (currentIndex: number, delta: number) => {
    const target = inputRefs.current[currentIndex + delta]
    if (target) {
      target.focus()
      target.select()
    }
  }

  if (error && !snapshot) return <div className="notice error">{error}</div>
  if (accountsReady === null) return <LoadingState label="正在准备本期盘点…" />
  if (!accountsReady) return <div className="page"><header className="page-header"><div><span className="eyebrow">QUICK SNAPSHOT</span><h1>新建资产盘点</h1></div></header><EmptyState title="先创建家庭成员和账户" description="盘点会自动复制全部未归档账户，但不会把上一期金额填入本期。" action={<Link className="button primary" to="/accounts">前往账户管理</Link>} /></div>
  if (!snapshot) return <LoadingState label="正在创建安全草稿…" />

  let inputIndex = -1
  return (
    <div className="page snapshot-page">
      <header className="page-header snapshot-header">
        <div><span className="eyebrow">QUICK SNAPSHOT</span><h1>新建资产盘点</h1><p><Keyboard size={15} /> Enter / ↓ 下一项，↑ 上一项，Tab 正常切换</p></div>
        <div className="snapshot-actions"><label>盘点日期<input type="date" value={snapshot.snapshot_date} onChange={(event) => updateDate(event.target.value)} /></label><span className="progress-text">已完成 {totals.completed_entries} / {totals.total_entries}</span><button className="button secondary" onClick={saveAll}><Save size={17} /> 保存草稿</button><button className="button primary" onClick={complete}><Sparkles size={17} /> 完成盘点</button></div>
      </header>
      <div className="autosave-line"><span className={saveStatus.includes('失败') || saveStatus.includes('尚未') ? 'status-dot error-dot' : 'status-dot'} /> {saveStatus}</div>
      {error && <div className="notice error">{error}</div>}

      {Object.entries(groups).map(([memberName, typeGroups]) => (
        <section className="snapshot-member" key={memberName}>
          <div className="member-heading"><div className="member-avatar">{memberName.slice(0, 1)}</div><div><h2>{memberName}</h2><p>{Object.values(typeGroups).flat().length} 个账户</p></div></div>
          {Object.entries(typeGroups).map(([type, entries]) => (
            <article className="panel entry-group" key={type}>
              <div className="entry-group-title"><h3>{ACCOUNT_TYPE_LABELS[type as keyof typeof ACCOUNT_TYPE_LABELS]}</h3><span>{entries.length} 项</span></div>
              <div className="entry-table">
                <div className="entry-row entry-head"><span>账户</span><span>上期</span><span>本期</span><span>变化</span></div>
                {entries.map((entry) => {
                  inputIndex += 1
                  const currentIndex = inputIndex
                  let currentCents: number | null = null
                  try { currentCents = parseAmountToCents(values[entry.id] ?? '') } catch { /* field shows the validation error */ }
                  const change = currentCents !== null && entry.previous_amount_cents !== null ? currentCents - entry.previous_amount_cents : null
                  const largeChange = change !== null && Math.abs(change) >= 100_000 && Math.abs(change) >= Math.max(Math.abs(entry.previous_amount_cents ?? 0), 10_000) * 5
                  return <div className="entry-row" key={entry.id}><div className="account-cell"><strong>{entry.account_name}</strong><small>{entry.institution || ACCOUNT_TYPE_LABELS[entry.account_type]}{!entry.include_in_net_worth ? ' · 不计入净资产' : ''}</small></div><span className="previous-value">{formatMoney(entry.previous_amount_cents)}</span><div className="input-cell"><span>¥</span><input ref={(element) => { inputRefs.current[currentIndex] = element }} className={`money-input ${fieldErrors[entry.id] ? 'invalid' : ''}`} inputMode="decimal" placeholder="请输入" value={values[entry.id] ?? ''} onChange={(event) => changeValue(entry.id, event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === 'ArrowDown') { event.preventDefault(); navigateInput(currentIndex, 1) } else if (event.key === 'ArrowUp') { event.preventDefault(); navigateInput(currentIndex, -1) } }} />{fieldErrors[entry.id] && <small className="field-error">{fieldErrors[entry.id]}</small>}</div><span className={change !== null && change < 0 ? 'negative' : 'positive'}>{formatMoney(change, true)}{largeChange && <span className="change-warning" title="较上期变化较大，请确认金额"><AlertTriangle size={14} /></span>}</span></div>
                })}
              </div>
            </article>
          ))}
        </section>
      ))}
      <div className="snapshot-summary"><div><span>本期资产</span><strong>{formatMoney(totals.total_assets_cents)}</strong></div><div><span>本期负债</span><strong>{formatMoney(totals.total_liabilities_cents)}</strong></div><div className="featured"><span>家庭净资产</span><strong>{formatMoney(totals.net_worth_cents)}</strong></div><div className="summary-confirm"><Check size={17} /> 所有汇总自动计算</div></div>
    </div>
  )
}
