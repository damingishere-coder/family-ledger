import { ArrowLeft, Check, Edit3, Save } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import LoadingState from '../components/LoadingState'
import { ACCOUNT_TYPE_LABELS } from '../lib/accounts'
import { api, errorMessage } from '../lib/api'
import { formatSnapshotMonth } from '../lib/month'
import { formatMoney } from '../lib/money'
import { useAmountEditor, useSaveBeforeLeave } from '../lib/useAmountEditor'
import type { Snapshot } from '../types'

export default function SnapshotDetailPage() {
  const { snapshotId } = useParams()
  const { snapshot, values, error, setError, saving, initialize, changeValue, saveAll, dirty } = useAmountEditor()
  const leaving = useSaveBeforeLeave(dirty, saveAll)
  const [editing, setEditing] = useState(false)
  const [message, setMessage] = useState('')

  const load = () => api.get<Snapshot>(`/snapshots/${snapshotId}`).then((data) => {
    initialize(data)
  }).catch((reason) => setError(errorMessage(reason)))
  useEffect(() => {
    void load()
  }, [snapshotId])

  const save = async () => {
    if (!snapshot) return
    setError('')
    if (await saveAll()) {
      setEditing(false); setMessage('修改已全部保存，汇总数据已重新计算。')
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
    <div className="page detail-page">
      <header className="page-header detail-header compact-page-header">
        <div><Link className="back-link" to="/history"><ArrowLeft size={16} /> 返回历史</Link><h1>{formatSnapshotMonth(snapshot.snapshot_date)} 家庭资产</h1><p>{formatSnapshotMonth(snapshot.snapshot_date)} · {snapshot.entries?.length ?? 0} 个账户 · {snapshot.status === 'completed' ? '已完成' : '草稿'}</p></div>
        <div className="button-row">{editing ? <><button className="button ghost" disabled={saving || leaving} onClick={() => { initialize(snapshot); setEditing(false) }}>取消</button><button className="button primary" disabled={saving || leaving} onClick={() => void save()}><Save size={17} /> 保存修改</button></> : <button className="button secondary" onClick={() => setEditing(true)}><Edit3 size={17} /> 编辑金额</button>}</div>
      </header>
      {message && <div className="notice success"><Check size={17} /> {message}</div>}
      {error && <div className="notice error">{error}</div>}
      <section className="summary-strip"><div><span>家庭总资产</span><strong>{formatMoney(snapshot.total_assets_cents)}</strong></div><div><span>家庭总负债</span><strong>{formatMoney(snapshot.total_liabilities_cents)}</strong></div><div className="featured"><span>家庭净资产</span><strong>{formatMoney(snapshot.net_worth_cents)}</strong></div></section>
      {Object.entries(groups).map(([memberName, entries]) => (
        <section className="panel table-panel detail-member-panel" key={memberName}>
          <div className="panel-header"><div><h2>{memberName}</h2><p>与上一期逐项比较</p></div></div>
          <div className="table-scroll"><table><thead><tr><th>账户</th><th>类型</th><th>上期</th><th>本期</th><th>变化</th><th>计入净资产</th></tr></thead><tbody>{entries?.map((entry) => <tr key={entry.id}><td><strong>{entry.account_name}</strong>{entry.institution && entry.institution !== entry.account_name ? <small>{entry.institution}</small> : null}{entry.legacy_raw_name && <details><summary className="text-link">原始记录</summary><small>{entry.source_file}{entry.source_location ? ` · ${entry.source_location}` : ''}</small><small>{entry.legacy_raw_name}：{entry.legacy_raw_value === '' ? '未填写' : entry.legacy_raw_value}</small></details>}</td><td><span className="type-tag">{ACCOUNT_TYPE_LABELS[entry.account_type]}</span></td><td>{formatMoney(entry.previous_amount_cents)}</td><td>{editing ? <input className="money-input compact" value={values[entry.id] ?? ''} aria-label={`${entry.account_name} 本期金额`} disabled={saving || leaving} onChange={(event) => changeValue(entry.id, event.target.value, false)} /> : formatMoney(entry.amount_cents)}</td><td className={entry.change_cents !== null && (['credit_card', 'other_liability'].includes(entry.account_type) ? entry.change_cents > 0 : entry.change_cents < 0) ? 'negative' : 'positive'}>{formatMoney(entry.change_cents, true)}</td><td>{entry.include_in_net_worth ? '计入' : '不计入'}{entry.amount_cents === null && <small>未填写金额</small>}</td></tr>)}</tbody></table></div>
        </section>
      ))}
      {snapshot.legacy_source && <section className="notice warning">此记录导入自 {snapshot.legacy_source}。原始值已保留。<Link className="text-link" to="/data/import">核对来源与修正归属</Link></section>}
    </div>
  )
}
