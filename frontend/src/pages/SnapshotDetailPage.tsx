import { ArrowLeft, Check, Edit3, Save } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import LoadingState from '../components/LoadingState'
import { api, errorMessage } from '../lib/api'
import { centsToInput, formatMoney, parseAmountToCents } from '../lib/money'
import type { Snapshot } from '../types'

export default function SnapshotDetailPage() {
  const { snapshotId } = useParams()
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [editing, setEditing] = useState(false)
  const [values, setValues] = useState<Record<number, string>>({})
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const load = () => api.get<Snapshot>(`/snapshots/${snapshotId}`).then((data) => {
    setSnapshot(data)
    setValues(Object.fromEntries((data.entries ?? []).map((entry) => [entry.id, centsToInput(entry.amount_cents)])))
  }).catch((reason) => setError(errorMessage(reason)))
  useEffect(() => {
    void load()
  }, [snapshotId])

  const save = async () => {
    if (!snapshot) return
    setError('')
    try {
      for (const entry of snapshot.entries ?? []) {
        const cents = parseAmountToCents(values[entry.id] ?? '')
        if (cents !== entry.amount_cents) {
          await api.put(`/snapshots/${snapshot.id}/entries/${entry.id}`, { amount_cents: cents })
        }
      }
      await load()
      setEditing(false)
      setMessage('修改已保存，汇总数据已重新计算。')
    } catch (reason) {
      setError(errorMessage(reason))
    }
  }

  if (error && !snapshot) return <div className="notice error">{error}</div>
  if (!snapshot) return <LoadingState />

  const groups = (snapshot.entries ?? []).reduce<Record<string, NonNullable<Snapshot['entries']>>>((result, entry) => {
    result[entry.member_name] ??= []
    result[entry.member_name].push(entry)
    return result
  }, {})
  return (
    <div className="page">
      <header className="page-header detail-header">
        <div><Link className="back-link" to="/history"><ArrowLeft size={16} /> 返回历史</Link><h1>{snapshot.title || `${snapshot.snapshot_date} 家庭资产`}</h1><p>{snapshot.snapshot_date} · {snapshot.entries?.length ?? 0} 个账户 · {snapshot.status === 'completed' ? '已完成' : '草稿'}</p></div>
        <div className="button-row">{editing ? <><button className="button ghost" onClick={() => { setEditing(false); load() }}>取消</button><button className="button primary" onClick={save}><Save size={17} /> 保存修改</button></> : <button className="button secondary" onClick={() => setEditing(true)}><Edit3 size={17} /> 编辑金额</button>}</div>
      </header>
      {message && <div className="notice success"><Check size={17} /> {message}</div>}
      {error && <div className="notice error">{error}</div>}
      <section className="summary-strip"><div><span>家庭总资产</span><strong>{formatMoney(snapshot.total_assets_cents)}</strong></div><div><span>家庭总负债</span><strong>{formatMoney(snapshot.total_liabilities_cents)}</strong></div><div className="featured"><span>家庭净资产</span><strong>{formatMoney(snapshot.net_worth_cents)}</strong></div></section>
      {Object.entries(groups).map(([memberName, entries]) => (
        <section className="panel table-panel" key={memberName}>
          <div className="panel-header"><div><h2>{memberName}</h2><p>与上一期逐项比较</p></div></div>
          <div className="table-scroll"><table><thead><tr><th>账户</th><th>类型</th><th>上期</th><th>本期</th><th>变化</th></tr></thead><tbody>{entries?.map((entry) => <tr key={entry.id}><td><strong>{entry.account_name}</strong>{entry.institution && entry.institution !== entry.account_name ? <small>{entry.institution}</small> : null}</td><td><span className="type-tag">{entry.account_type}</span></td><td>{formatMoney(entry.previous_amount_cents)}</td><td>{editing ? <input className="money-input compact" value={values[entry.id] ?? ''} onChange={(event) => setValues((current) => ({ ...current, [entry.id]: event.target.value }))} /> : formatMoney(entry.amount_cents)}</td><td className={entry.change_cents !== null && entry.change_cents < 0 ? 'negative' : 'positive'}>{formatMoney(entry.change_cents, true)}</td></tr>)}</tbody></table></div>
        </section>
      ))}
      {snapshot.legacy_source && <section className="notice warning">此记录导入自 {snapshot.legacy_source}。原始值已保留，导入差异请在“数据管理”查看。</section>}
    </div>
  )
}
