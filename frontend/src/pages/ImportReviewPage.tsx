import { useRef, useState } from 'react'
import { ArrowLeft, Check, FileUp, RefreshCw } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api, errorMessage } from '../lib/api'
import { ACCOUNT_TYPE_LABELS, ACCOUNT_TYPE_OPTIONS } from '../lib/accounts'
import { formatMoney } from '../lib/money'
import type { AccountType, ImportRecord, Totals } from '../types'

type EntryValues = { member_name: string; account_name: string; account_type: AccountType;
  amount_cents: number | null; include_in_net_worth: boolean }
type Choice = { member_name: string; account_type: string }
type ReviewStatus = 'new' | 'update' | 'unchanged' | 'conflict' | 'needs_review' | 'blocked' | 'ignored'
interface Review {
  token: string; review_id: string; files: string[]; members: string[]; mappings: Record<string, Choice>
  groups: Array<{ key: string; account_name: string; source_member: string | null; member_name: string | null;
    account_type: AccountType; needs_review: boolean; direction_unclear: boolean; months: string[]; sources: string[] }>
  months: Array<{ month: string | null; source_sheet: string | null; source_date: string; snapshot_id: number | null;
    status: ReviewStatus; errors: string[]; warnings: string[]; calculated_summary: Totals;
    entries: Array<{ key: string; entry_id: number | null; source_file: string; source_location: string;
      raw_name: string; raw_value: string; source_member: string | null; before: EntryValues | null;
      after: EntryValues; status: ReviewStatus; reason: string }> }>
  evidence: Array<{ month: string; account: string; source: string; location: string;
    markdown_cents: number | null; excel_cents: number | null; message: string }>
}
const labels: Record<ReviewStatus, string> = { new: '新增月份', update: '可修正', unchanged: '无变化',
  conflict: '保留原记录', needs_review: '待确认归属或类型', blocked: '来源待核对', ignored: '辅助页，忽略' }

export default function ImportReviewPage() {
  const input = useRef<HTMLInputElement>(null)
  const [files, setFiles] = useState<File[]>([])
  const [review, setReview] = useState<Review | null>(null)
  const [choices, setChoices] = useState<Record<string, Choice>>({})
  const [selected, setSelected] = useState<string[]>([])
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [dirty, setDirty] = useState(false)
  const [showAll, setShowAll] = useState(false)
  const [result, setResult] = useState<(ImportRecord & { applied_months: string[]; backup_filename: string }) | null>(null)

  const accept = (data: Review) => {
    setReview(data)
    setChoices(Object.fromEntries(data.groups.map(g => [g.key, {
      member_name: g.member_name ?? '', account_type: g.direction_unclear && g.needs_review ? '' : g.account_type,
    }])))
    setSelected(data.months.filter(m => m.status === 'new' || m.status === 'update').map(m => m.month!))
    setDirty(false)
  }
  const preview = async (chosen: File[]) => {
    if (!chosen.length) return
    setFiles(chosen); setReview(null); setResult(null); setError('')
    if (chosen.length > 5 || chosen.some(f => f.size > 20 * 1024 * 1024) || chosen.reduce((n, f) => n + f.size, 0) > 40 * 1024 * 1024) {
      setError('一次最多 5 个文件，单个不超过 20MB，合计不超过 40MB。'); return
    }
    setBusy('正在核对文件与现有记录…')
    try { accept(await api.uploadMany<Review>('/import/batch/preview', chosen)) }
    catch (reason) { setError(errorMessage(reason)) }
    finally { setBusy('') }
  }
  const recalculate = async () => {
    if (!review) return
    setBusy('正在重新核对…'); setError('')
    try {
      const mappings = Object.fromEntries(Object.entries(choices).filter(([, c]) => c.member_name && c.account_type))
      accept(await api.post<Review>('/import/batch/review', { token: review.token, mappings }))
    } catch (reason) { setError(errorMessage(reason)) }
    finally { setBusy('') }
  }
  const confirm = async () => {
    if (!review || dirty || busy || !selected.length) return
    setBusy('正在备份并保存所选月份…'); setError('')
    try { setResult(await api.post('/import/batch/confirm', { token: review.token, review_id: review.review_id, months: selected })) }
    catch (reason) { setError(errorMessage(reason)) }
    finally { setBusy('') }
  }
  const setChoice = (key: string, field: keyof Choice, value: string) => {
    setChoices(current => ({ ...current, [key]: { ...current[key], [field]: value } })); setDirty(true)
  }
  const pending = review?.groups.filter(g => g.needs_review).length ?? 0
  const groups = review?.groups.filter(g => showAll || g.needs_review) ?? []
  return <div className="page import-review-page">
    <Link className="back-link" to="/data"><ArrowLeft size={16} /> 返回数据管理</Link>
    <header className="page-header"><div><h1>导入与核对历史</h1><p>Excel 提供金额，Markdown 补充日期与账户信息。核对完成后再写入。</p></div></header>
    <ol className="workflow-steps" aria-label="导入步骤"><li className={!review ? 'active' : ''}>1 选择文件</li><li className={review && !result ? 'active' : ''}>2 核对账户与月份</li><li className={result ? 'active' : ''}>3 确认结果</li></ol>
    {error && <div className="notice error" role="alert">{error}</div>}
    {busy && <div className="notice" role="status">{busy}</div>}
    {result ? <section className="panel review-complete"><Check size={32} /><h2>已保存 {result.applied_months.length} 个月份</h2><p>新增或修正 {result.success_rows} 条明细。未选择的月份和冲突记录保持原样。</p><p className="muted">写入前备份：{result.backup_filename}</p><div className="button-row"><Link className="button primary" to="/history">查看历史记录</Link><button className="button secondary" onClick={() => void preview(files)}>再次核对</button></div></section> : <>
      <section className="panel upload-section"><div><h2>{review ? '本次来源文件' : '一起选择有关联的旧表格'}</h2><p>可以同时选择账单 Excel 和两份年度 Markdown；原始文件不会被修改。</p>{files.length > 0 && <ul className="source-files">{files.map(f => <li key={f.name}>{f.name}</li>)}</ul>}</div><button className="button primary" disabled={!!busy} onClick={() => input.current?.click()}><FileUp size={18} /> {files.length ? '重新选择文件' : '选择文件'}</button><input ref={input} type="file" hidden multiple accept=".xlsx,.xlsm,.csv,.md,.markdown,.txt" onChange={e => { const chosen = Array.from(e.target.files ?? []); e.target.value = ''; void preview(chosen) }} /></section>
      {review && <>
        <section className="panel mapping-section"><div className="panel-header"><div><h2>账户归属与类型</h2><p>{pending ? `${pending} 个账户需要确认。原表没有标明成员的项目不会自动归入家庭公共。` : '有明确来源的账户已匹配，你仍可以检查全部账户。'}</p></div><button className="button secondary" onClick={() => setShowAll(!showAll)}>{showAll ? '只看待确认' : `检查全部 ${review.groups.length} 个账户`}</button></div>
          <div className="table-scroll"><table className="mapping-table"><thead><tr><th>原表账户与位置</th><th>原表成员</th><th>导入到成员</th><th>账户类型</th></tr></thead><tbody>{groups.map(g => <tr key={g.key}><td><strong>{g.account_name}</strong><small>{g.months.length} 个月份</small><details><summary>查看原表位置</summary>{g.sources.map(source => <small key={source}>{source}</small>)}</details></td><td>{g.source_member || '未标明'}{g.direction_unclear && <small>请核对谁欠谁</small>}</td><td><select aria-label={`${g.account_name} 所属成员`} disabled={!!busy} value={choices[g.key]?.member_name ?? ''} onChange={e => setChoice(g.key, 'member_name', e.target.value)}><option value="">请选择成员</option>{review.members.map(m => <option key={m}>{m}</option>)}</select></td><td><select aria-label={`${g.account_name} 账户类型`} disabled={!!busy} value={choices[g.key]?.account_type ?? ''} onChange={e => setChoice(g.key, 'account_type', e.target.value)}><option value="">请选择收付款方向</option>{ACCOUNT_TYPE_OPTIONS.map(([type, label]) => <option key={type} value={type}>{type === 'receivable' ? '待收欠款（别人欠我们）' : type === 'other_liability' ? '其他负债（我们欠别人）' : label}</option>)}</select></td></tr>)}</tbody></table></div>
          {!groups.length && <p className="inline-empty">没有需要确认的账户。</p>}
          <div className="panel-footer"><span className="muted">确认的归属与类型会用于后续同类导入；不计入标记按每月原表保留。</span><button className="button secondary" disabled={!!busy} onClick={() => void recalculate()}><RefreshCw size={16} /> {dirty ? '应用选择并重新核对' : '刷新核对结果'}</button></div>
        </section>
        <section className="panel month-review"><div className="panel-header"><div><h2>逐月核对</h2><p>无变化的月份无需重复保存；存在冲突的月份保留原记录。</p></div><span>{review.months.length} 个来源项目</span></div>
          {dirty && <div className="notice warning">账户选择已改变，请先点击“应用选择并重新核对”。</div>}
          {review.months.map((m, index) => <details className="month-review-item" key={`${m.source_sheet}-${m.month}-${index}`}><summary><label onClick={e => e.stopPropagation()}><input type="checkbox" aria-label={`选择 ${m.month ?? m.source_sheet}`} checked={selected.includes(m.month!)} disabled={!!busy || dirty || !['new', 'update'].includes(m.status)} onChange={e => setSelected(current => e.target.checked ? [...current, m.month!] : current.filter(value => value !== m.month))} /><strong>{m.month ?? m.source_sheet ?? '无有效日期'}</strong></label><span className={`review-status ${m.status}`}>{labels[m.status]}</span><span className="month-review-money">拟导入净资产 {formatMoney(m.calculated_summary.net_worth_cents)}</span><span>展开明细</span></summary>
            <div className="month-review-content"><p className="muted">来源日期：{m.source_date || '未提供'}{m.source_sheet ? ` · 工作表 ${m.source_sheet}` : ''}{m.snapshot_id && <> · <Link className="text-link" to={`/snapshots/${m.snapshot_id}`}>查看现有记录</Link></>}</p>
              {m.errors.map((message, i) => <div className="notice error" key={i}>{message}</div>)}
              {m.warnings.length > 0 && <details className="review-warnings"><summary>{m.warnings.length} 条来源说明</summary><ul>{m.warnings.map((message, i) => <li key={i}>{message}</li>)}</ul></details>}
              <div className="table-scroll"><table><thead><tr><th>原始记录</th><th>现有记录</th><th>拟导入记录</th><th>计入净资产</th><th>处理说明</th></tr></thead><tbody>{m.entries.map((e, i) => <tr key={i}><td><strong>{e.raw_name}</strong><small>{e.source_file} · {e.source_location}</small><small>原值：{e.raw_value === '' ? '未填写' : e.raw_value}</small></td><td>{e.before ? <>{e.before.member_name} · {ACCOUNT_TYPE_LABELS[e.before.account_type]}<small>{formatMoney(e.before.amount_cents)}</small><small>{e.before.include_in_net_worth ? '计入' : '不计入'}</small></> : '—'}</td><td>{e.after.member_name} · {ACCOUNT_TYPE_LABELS[e.after.account_type]}<small>{formatMoney(e.after.amount_cents)}</small></td><td>{e.after.include_in_net_worth ? '计入' : '不计入'}{e.after.amount_cents === null && <small>金额未填写</small>}</td><td>{e.reason}</td></tr>)}</tbody></table></div>
            </div></details>)}
        </section>
        {review.evidence.some(e => e.markdown_cents !== e.excel_cents) && <details className="panel cross-file-evidence"><summary>查看 Excel 与 Markdown 的金额差异（采用 Excel）</summary><div className="table-scroll"><table><thead><tr><th>月份 / 账户</th><th>Markdown</th><th>Excel</th><th>来源位置</th></tr></thead><tbody>{review.evidence.filter(e => e.markdown_cents !== e.excel_cents).map((e, i) => <tr key={i}><td>{e.month} · {e.account}</td><td>{formatMoney(e.markdown_cents)}</td><td>{formatMoney(e.excel_cents)}</td><td>{e.source} · {e.location}</td></tr>)}</tbody></table></div></details>}
        <div className="review-confirm-bar"><div><strong>已选 {selected.length} 个月份</strong><p>保存前自动备份。仅处理所选月份，原表和手工记录保持原样。</p></div><button className="button primary" disabled={!!busy || dirty || !selected.length} onClick={() => void confirm()}>确认保存所选月份</button></div>
      </>}
    </>}
  </div>
}
