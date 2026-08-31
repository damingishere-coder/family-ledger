import { AlertTriangle, ArchiveRestore, DatabaseBackup, Download, FileSpreadsheet, FileText, Upload } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api, errorMessage } from '../lib/api'
import type { ImportRecord } from '../types'

export default function DataPage() {
  const legacyInput = useRef<HTMLInputElement>(null)
  const tableInput = useRef<HTMLInputElement>(null)
  const restoreInput = useRef<HTMLInputElement>(null)
  const [imports, setImports] = useState<ImportRecord[]>([])
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = () => api.get<ImportRecord[]>('/imports').then(setImports).catch(() => undefined)
  useEffect(() => {
    void load()
  }, [])

  const upload = async (path: string, file: File) => {
    setBusy(true); setError(''); setMessage('')
    try {
      const result = await api.upload<ImportRecord>(path, file)
      setMessage(`导入完成：成功 ${result.success_rows} 行，警告 ${result.warning_rows} 行，错误 ${result.error_rows} 行。`)
      load()
    } catch (reason) { setError(errorMessage(reason)) } finally { setBusy(false) }
  }

  const backup = async () => {
    setBusy(true); setError('')
    try {
      const result = await api.post<{ filename: string }>('/backup')
      setMessage(`数据库备份已生成：${result.filename}`)
    } catch (reason) { setError(errorMessage(reason)) } finally { setBusy(false) }
  }

  const restore = async (file: File) => {
    if (!window.confirm('恢复会用备份内容替换当前全部成员、账户和历史快照。系统会先保存一份回滚数据库。确认继续吗？')) return
    setBusy(true); setError(''); setMessage('')
    try {
      const result = await api.upload<{ rollback_backup: string }>('/restore', file)
      setMessage(`恢复完成。恢复前数据库保存在 ${result.rollback_backup}。`)
      load()
    } catch (reason) { setError(errorMessage(reason)) } finally { setBusy(false) }
  }

  return (
    <div className="page">
      <header className="page-header"><div><span className="eyebrow">DATA & SAFETY</span><h1>数据管理</h1><p>导入不会偷偷纠正历史；完整备份可在另一台本地环境恢复。</p></div></header>
      {message && <div className="notice success">{message}</div>}
      {error && <div className="notice error">{error}</div>}
      <section className="data-grid">
        <article className="panel data-card"><div className="data-icon"><Upload size={22} /></div><h2>导入历史数据</h2><p>Markdown 会解析日期、成员、账户、空值和负数；CSV/XLSX 使用规范表头。名称差异只提示，不自动合并。</p><div className="button-row"><button className="button secondary" disabled={busy} onClick={() => legacyInput.current?.click()}><FileText size={17} /> 历史 Markdown</button><button className="button secondary" disabled={busy} onClick={() => tableInput.current?.click()}><FileSpreadsheet size={17} /> CSV / Excel</button></div><input ref={legacyInput} hidden type="file" accept=".md,.markdown,text/markdown,text/plain" onChange={(event) => { const file = event.target.files?.[0]; if (file) upload('/import/legacy', file); event.target.value = '' }} /><input ref={tableInput} hidden type="file" accept=".csv,.xlsx,.xlsm" onChange={(event) => { const file = event.target.files?.[0]; if (file) upload('/import/tabular', file); event.target.value = '' }} /></article>
        <article className="panel data-card"><div className="data-icon"><Download size={22} /></div><h2>导出数据</h2><p>JSON 是完整、可恢复的备份；CSV 与 Excel 便于人工检查和继续分析。</p><div className="button-row wrap"><a className="button secondary" href="/api/export/json"><Download size={17} /> 完整 JSON</a><a className="button secondary" href="/api/export/csv">导出 CSV</a><a className="button secondary" href="/api/export/excel">导出 Excel</a></div></article>
        <article className="panel data-card"><div className="data-icon"><DatabaseBackup size={22} /></div><h2>数据库备份</h2><p>每天首次启动自动生成一致性 SQLite 备份并保留最近 30 份，也可以立即手动备份。</p><button className="button primary" disabled={busy} onClick={backup}><DatabaseBackup size={17} /> 立即备份</button></article>
        <article className="panel data-card danger-card"><div className="data-icon"><ArchiveRestore size={22} /></div><h2>恢复完整备份</h2><p>仅接受本系统导出的 JSON。恢复前会先生成回滚数据库，结构或外键校验失败时不会提交。</p><button className="button danger-button" disabled={busy} onClick={() => restoreInput.current?.click()}><ArchiveRestore size={17} /> 选择备份并恢复</button><input ref={restoreInput} hidden type="file" accept=".json,application/json" onChange={(event) => { const file = event.target.files?.[0]; if (file) restore(file); event.target.value = '' }} /></article>
      </section>
      <section className="panel import-history"><div className="panel-header"><div><h2>导入记录</h2><p>原始值、系统重算与警告可追溯</p></div></div>{imports.length ? <div className="import-list">{imports.map((record) => <details key={record.id}><summary><div><strong>{record.source_filename}</strong><span>{new Date(record.imported_at).toLocaleString('zh-CN')}</span></div><div className="import-badges"><span className={`status-badge ${record.status}`}>{record.status}</span><span>成功 {record.success_rows}</span><span>警告 {record.warning_rows}</span><span>错误 {record.error_rows}</span></div></summary><div className="import-report">{record.report.warnings?.length ? <div><h3><AlertTriangle size={16} /> 警告</h3><ul>{record.report.warnings.slice(0, 50).map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul></div> : <p>没有警告。</p>}{record.report.errors?.length ? <div><h3>错误</h3><ul>{record.report.errors.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul></div> : null}</div></details>)}</div> : <div className="inline-empty">还没有导入记录。</div>}</section>
      <div className="notice warning"><AlertTriangle size={18} /><div><strong>数据安全提示</strong><p>请定期把完整 JSON 备份复制到项目目录以外的位置。项目不会把家庭财务数据上传到互联网。</p></div></div>
    </div>
  )
}
