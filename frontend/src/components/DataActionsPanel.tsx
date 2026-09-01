import { DatabaseBackup, Download, FileSpreadsheet, FileText, Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { api, errorMessage } from '../lib/api'
import type { ImportRecord } from '../types'

interface DataActionsPanelProps {
  compact?: boolean
  onMessage?: (message: string) => void
  onError?: (message: string) => void
  onChanged?: () => void
}

export default function DataActionsPanel({
  compact = false,
  onMessage,
  onError,
  onChanged,
}: DataActionsPanelProps) {
  const legacyInput = useRef<HTMLInputElement>(null)
  const tableInput = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)

  const upload = async (path: string, file: File) => {
    setBusy(true)
    try {
      const result = await api.upload<ImportRecord>(path, file)
      onMessage?.(`导入完成：成功 ${result.success_rows} 行，警告 ${result.warning_rows} 行，错误 ${result.error_rows} 行。`)
      onChanged?.()
    } catch (reason) {
      onError?.(errorMessage(reason))
    } finally {
      setBusy(false)
    }
  }

  const backup = async () => {
    setBusy(true)
    try {
      const result = await api.post<{ filename: string }>('/backup')
      onMessage?.(`数据库备份已生成：${result.filename}`)
    } catch (reason) {
      onError?.(errorMessage(reason))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className={`panel data-actions-panel ${compact ? 'compact' : ''}`}>
      <div className="panel-header">
        <div><h2>数据管理</h2><p>{compact ? '常用导入、导出与备份' : '本地数据的导入、导出与安全备份'}</p></div>
      </div>
      <div className="data-action-list">
        {!compact && (
          <button className="data-action" disabled={busy} onClick={() => legacyInput.current?.click()}>
            <span className="data-action-icon"><FileText size={17} /></span>
            <span><strong>导入历史 Markdown</strong><small>保留原值并生成校验警告</small></span>
          </button>
        )}
        <button className="data-action" disabled={busy} onClick={() => tableInput.current?.click()}>
          <span className="data-action-icon"><Upload size={17} /></span>
          <span><strong>导入历史数据</strong><small>支持 CSV 与 Excel 文件</small></span>
        </button>
        <a className="data-action" href="/api/export/excel">
          <span className="data-action-icon"><FileSpreadsheet size={17} /></span>
          <span><strong>导出 Excel</strong><small>便于人工检查与分析</small></span>
        </a>
        {!compact && (
          <a className="data-action" href="/api/export/csv">
            <span className="data-action-icon"><Download size={17} /></span>
            <span><strong>导出 CSV</strong><small>导出规范化明细数据</small></span>
          </a>
        )}
        <a className="data-action" href="/api/export/json">
          <span className="data-action-icon"><Download size={17} /></span>
          <span><strong>导出 JSON</strong><small>完整、可恢复的数据备份</small></span>
        </a>
        <button className="data-action" disabled={busy} onClick={backup}>
          <span className="data-action-icon"><DatabaseBackup size={17} /></span>
          <span><strong>备份全部数据</strong><small>立即生成一致性数据库备份</small></span>
        </button>
      </div>
      <input ref={legacyInput} hidden type="file" accept=".md,.markdown,text/markdown,text/plain" onChange={(event) => { const file = event.target.files?.[0]; if (file) void upload('/import/legacy', file); event.target.value = '' }} />
      <input ref={tableInput} hidden type="file" accept=".csv,.xlsx,.xlsm" onChange={(event) => { const file = event.target.files?.[0]; if (file) void upload('/import/tabular', file); event.target.value = '' }} />
    </section>
  )
}
