import { AlertTriangle, ArchiveRestore, ShieldCheck } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import DataActionsPanel from '../components/DataActionsPanel'
import { api, errorMessage } from '../lib/api'
import type { ImportRecord } from '../types'

export default function DataPage() {
  const restoreInput = useRef<HTMLInputElement>(null)
  const [imports, setImports] = useState<ImportRecord[]>([])
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = () => api.get<ImportRecord[]>('/imports').then(setImports).catch(() => undefined)
  useEffect(() => {
    void load()
  }, [])

  const restore = async (file: File) => {
    if (!window.confirm('恢复会用备份内容替换当前全部成员、账户和历史快照。系统会先保存一份回滚数据库。确认继续吗？')) return
    setBusy(true); setError(''); setMessage('')
    try {
      const result = await api.upload<{ rollback_backup: string }>('/restore', file)
      setMessage(`恢复完成。恢复前数据库保存在 ${result.rollback_backup}。`)
      load()
    } catch (reason) { setError(errorMessage(reason)) } finally { setBusy(false) }
  }

  const showMessage = (value: string) => { setError(''); setMessage(value) }
  const showError = (value: string) => { setMessage(''); setError(value) }

  return (
    <div className="page data-page">
      <header className="page-header compact-page-header"><div><h1>数据管理</h1><p>导入不擅自修正历史，完整备份始终保存在本地。</p></div></header>
      {message && <div className="notice success">{message}</div>}
      {error && <div className="notice error">{error}</div>}

      <section className="data-management-grid">
        <DataActionsPanel onChanged={load} onMessage={showMessage} onError={showError} />
        <div className="data-safety-column">
          <article className="panel safety-card">
            <div className="safety-icon"><ShieldCheck size={21} /></div>
            <div><h2>本地安全机制</h2><p>每天首次启动生成一致性 SQLite 备份，保留最近 30 份。系统不会上传家庭财务数据。</p></div>
          </article>
          <article className="panel restore-card">
            <div><h2>恢复完整备份</h2><p>仅接受本系统导出的 JSON。恢复前会生成回滚数据库，结构或外键校验失败时不会提交。</p></div>
            <button className="button danger-button" disabled={busy} onClick={() => restoreInput.current?.click()}><ArchiveRestore size={16} /> 选择备份并恢复</button>
            <input ref={restoreInput} hidden type="file" accept=".json,application/json" onChange={(event) => { const file = event.target.files?.[0]; if (file) void restore(file); event.target.value = '' }} />
          </article>
        </div>
      </section>

      <section className="panel import-history">
        <div className="panel-header"><div><h2>导入记录</h2><p>原始值、系统重算与警告均可追溯</p></div><span className="record-count">{imports.length} 条记录</span></div>
        {imports.length ? <div className="import-list">{imports.map((record) => <details key={record.id}><summary><div><strong>{record.source_filename}</strong><span>{new Date(record.imported_at).toLocaleString('zh-CN')}</span></div><div className="import-badges"><span className={`status-badge ${record.status}`}>{record.status}</span><span>成功 {record.success_rows}</span><span>警告 {record.warning_rows}</span><span>错误 {record.error_rows}</span></div></summary><div className="import-report">{record.report.warnings?.length ? <div><h3><AlertTriangle size={15} /> 警告</h3><ul>{record.report.warnings.slice(0, 50).map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul></div> : <p>没有警告。</p>}{record.report.errors?.length ? <div><h3>错误</h3><ul>{record.report.errors.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul></div> : null}</div></details>)}</div> : <div className="inline-empty">还没有导入记录。</div>}
      </section>
      <div className="notice warning"><AlertTriangle size={17} /><div><strong>数据安全提示</strong><p>请定期把完整 JSON 备份复制到项目目录以外的位置。</p></div></div>
    </div>
  )
}
