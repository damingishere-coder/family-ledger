import {
  AlertTriangle,
  CheckCircle2,
  DatabaseBackup,
  Download,
  FileSpreadsheet,
  FileText,
  LoaderCircle,
  Upload,
  X,
} from 'lucide-react'
import { useRef, useState } from 'react'
import { api, errorMessage } from '../lib/api'
import { formatMoney } from '../lib/money'
import type { ImportPreview, ImportRecord } from '../types'

type ImportKind = 'legacy' | 'tabular'
type ImportPhase = 'previewing' | 'ready' | 'error' | 'importing' | 'completed'

interface ImportDialogState {
  kind: ImportKind
  file: File
  phase: ImportPhase
  preview?: ImportPreview
  result?: ImportRecord
  error?: string
}

interface DataActionsPanelProps {
  compact?: boolean
  onMessage?: (message: string) => void
  onError?: (message: string) => void
  onChanged?: () => void | Promise<void>
}

const MAX_UPLOAD_BYTES = 20 * 1024 * 1024

const IMPORT_PATHS: Record<ImportKind, { preview: string; confirm: string }> = {
  legacy: { preview: '/import/legacy/preview', confirm: '/import/legacy' },
  tabular: { preview: '/import/tabular/preview', confirm: '/import/tabular' },
}

const PREVIEW_STATUS_LABELS: Record<ImportPreview['snapshots'][number]['status'], string> = {
  importable: '可导入',
  duplicate: '自然月重复，跳过',
  blocked: '已阻止',
  ignored: '已忽略',
}

function formatSummary(label: string, summary: {
  total_assets_cents?: number | null
  total_liabilities_cents?: number | null
  net_worth_cents?: number | null
}): string | null {
  const values = [
    summary.total_assets_cents,
    summary.total_liabilities_cents,
    summary.net_worth_cents,
  ]
  if (values.every((value) => value === null || value === undefined)) return null
  return `${label}：资产 ${formatMoney(values[0])} / 负债 ${formatMoney(values[1])} / 净资产 ${formatMoney(values[2])}`
}

function formatSourceType(preview: ImportPreview): string {
  if (preview.source_type === 'markdown') return 'Markdown'
  if (preview.source_type === 'csv') return 'CSV'
  return 'XLSX / XLSM'
}

function formatEncoding(encoding: string | null): string | null {
  if (encoding === 'utf-8-sig') return 'UTF-8'
  if (encoding === 'gb18030') return 'GB18030'
  return encoding
}

export default function DataActionsPanel({
  compact = false,
  onMessage,
  onError,
  onChanged,
}: DataActionsPanelProps) {
  const legacyInput = useRef<HTMLInputElement>(null)
  const tableInput = useRef<HTMLInputElement>(null)
  const [backupBusy, setBackupBusy] = useState(false)
  const [dialog, setDialog] = useState<ImportDialogState | null>(null)
  const importBusy = dialog?.phase === 'previewing' || dialog?.phase === 'importing'
  const busy = backupBusy || importBusy

  const preview = async (kind: ImportKind, file: File) => {
    if (file.size > MAX_UPLOAD_BYTES) {
      setDialog({ kind, file, phase: 'error', error: '文件超过 20MB 限制' })
      return
    }
    setDialog({ kind, file, phase: 'previewing' })
    try {
      const result = await api.upload<ImportPreview>(IMPORT_PATHS[kind].preview, file)
      setDialog({ kind, file, phase: 'ready', preview: result })
    } catch (reason) {
      setDialog({ kind, file, phase: 'error', error: errorMessage(reason) })
    }
  }

  const confirmImport = async () => {
    if (!dialog?.preview || dialog.phase !== 'ready') return
    const { kind, file, preview: previewResult } = dialog
    setDialog({ kind, file, phase: 'importing', preview: previewResult })
    let result: ImportRecord
    try {
      result = await api.upload<ImportRecord>(IMPORT_PATHS[kind].confirm, file)
    } catch (reason) {
      setDialog({ kind, file, phase: 'error', preview: previewResult, error: errorMessage(reason) })
      return
    }
    setDialog({ kind, file, phase: 'completed', preview: previewResult, result })
    onMessage?.(`导入完成：成功 ${result.success_rows} 行，警告 ${result.warning_rows} 行，错误 ${result.error_rows} 行。`)
    try {
      await onChanged?.()
    } catch (reason) {
      onError?.(`导入已经完成，但页面刷新失败：${errorMessage(reason)}`)
    }
  }

  const chooseAgain = () => {
    if (!dialog || importBusy) return
    const input = dialog.kind === 'legacy' ? legacyInput : tableInput
    input.current?.click()
  }

  const closeDialog = () => {
    if (!importBusy) setDialog(null)
  }

  const backup = async () => {
    setBackupBusy(true)
    try {
      const result = await api.post<{ filename: string }>('/backup')
      onMessage?.(`数据库备份已生成：${result.filename}`)
    } catch (reason) {
      onError?.(errorMessage(reason))
    } finally {
      setBackupBusy(false)
    }
  }

  const selectFile = (kind: ImportKind, input: HTMLInputElement) => {
    const file = input.files?.[0]
    input.value = ''
    if (file) void preview(kind, file)
  }

  return (
    <>
      <section className={`panel data-actions-panel ${compact ? 'compact' : ''}`}>
        <div className="panel-header">
          <div><h2>数据管理</h2><p>{compact ? '常用导入、导出与备份' : '本地数据的导入、导出与安全备份'}</p></div>
        </div>
        <div className="data-action-list">
          {!compact && (
            <button type="button" className="data-action" disabled={busy} onClick={() => legacyInput.current?.click()}>
              <span className="data-action-icon"><FileText size={17} /></span>
              <span><strong>导入历史 Markdown</strong><small>选择后先预览，再确认导入</small></span>
            </button>
          )}
          <button type="button" className="data-action" disabled={busy} onClick={() => tableInput.current?.click()}>
            <span className="data-action-icon"><Upload size={17} /></span>
            <span><strong>导入历史数据</strong><small>支持 .CSV、.XLSX 与 .XLSM</small></span>
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
          <button type="button" className="data-action" disabled={busy} onClick={backup}>
            <span className="data-action-icon"><DatabaseBackup size={17} /></span>
            <span><strong>备份全部数据</strong><small>{backupBusy ? '正在生成备份…' : '立即生成一致性数据库备份'}</small></span>
          </button>
        </div>
        <input ref={legacyInput} hidden type="file" accept=".md,.markdown,.txt,text/markdown,text/plain" onChange={(event) => selectFile('legacy', event.currentTarget)} />
        <input ref={tableInput} hidden type="file" accept=".csv,.xlsx,.xlsm" onChange={(event) => selectFile('tabular', event.currentTarget)} />
      </section>

      {dialog && (
        <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && closeDialog()}>
          <div className="modal import-preview-modal" role="dialog" aria-modal="true" aria-labelledby="import-preview-title">
            <div className="modal-header">
              <div>
                <h2 id="import-preview-title">{dialog.phase === 'completed' ? '导入完成' : '导入历史数据'}</h2>
                <p>{dialog.file.name}</p>
              </div>
              <button type="button" className="icon-button" aria-label="关闭导入窗口" disabled={importBusy} onClick={closeDialog}><X size={19} /></button>
            </div>

            <div className="import-preview-body" aria-live="polite">
              {dialog.phase === 'previewing' && (
                <div className="import-progress" role="status"><LoaderCircle className="spin" size={22} /> 正在解析文件，请稍候…</div>
              )}

              {dialog.phase === 'error' && (
                <div className="notice error import-dialog-notice"><AlertTriangle size={18} /><div><strong>无法继续导入</strong><p>{dialog.error}</p></div></div>
              )}

              {(dialog.phase === 'ready' || dialog.phase === 'importing') && dialog.preview && (
                <>
                  <div className="import-preview-summary">
                    <div><span>文件格式</span><strong>{formatSourceType(dialog.preview)}</strong></div>
                    <div><span>来源项目</span><strong>{dialog.preview.total_snapshots}</strong></div>
                    <div><span>有效明细</span><strong>{dialog.preview.importable_rows} 行</strong></div>
                    <div><span>阻止 / 忽略</span><strong>{dialog.preview.blocked_snapshots} / {dialog.preview.ignored_snapshots}</strong></div>
                  </div>
                  {formatEncoding(dialog.preview.detected_encoding) && <p className="import-encoding">文本编码：{formatEncoding(dialog.preview.detected_encoding)}</p>}
                  <div className="import-preview-list">
                    {dialog.preview.snapshots.map((snapshot, index) => (
                      <div className={snapshot.will_skip ? 'will-skip' : ''} key={`${snapshot.source_sheet ?? 'source'}-${snapshot.snapshot_date ?? index}`}>
                        <strong>{snapshot.source_sheet ? `${snapshot.source_sheet} · ` : ''}{snapshot.snapshot_date ?? '无有效日期'}</strong>
                        <span>{snapshot.row_count} 行 · {PREVIEW_STATUS_LABELS[snapshot.status]} · {snapshot.layout}</span>
                        {snapshot.source_date && <small>源文件日期：{snapshot.source_date}</small>}
                        {formatSummary('来源汇总', snapshot.source_summary) && <small>{formatSummary('来源汇总', snapshot.source_summary)}</small>}
                        <small>{formatSummary('计算汇总', snapshot.calculated_summary)}</small>
                        {snapshot.differences.length > 0 && (
                          <small>{snapshot.differences.map((difference) => `${difference.field}：来源 ${formatMoney(difference.source_cents)} / 计算 ${formatMoney(difference.calculated_cents)}${difference.explained ? '（可解释）' : ''}`).join('；')}</small>
                        )}
                        {snapshot.blocking_errors.length > 0 && <small>{snapshot.blocking_errors.join('；')}</small>}
                      </div>
                    ))}
                  </div>
                  {dialog.preview.warnings.length > 0 && (
                    <details className="import-preview-warnings">
                      <summary>查看 {dialog.preview.warnings.length} 条警告</summary>
                      <ul>{dialog.preview.warnings.slice(0, 50).map((warning, index) => <li key={`${index}-${warning}`}>{warning}</li>)}</ul>
                    </details>
                  )}
                  {dialog.preview.importable_rows === 0 && (
                    <div className="notice warning import-dialog-notice"><AlertTriangle size={18} /><div><strong>没有新数据可导入</strong><p>请查看重复、阻止或忽略原因；系统不会写入这些项目。</p></div></div>
                  )}
                  {dialog.phase === 'importing' && <div className="import-progress" role="status"><LoaderCircle className="spin" size={22} /> 正在写入本地数据库…</div>}
                </>
              )}

              {dialog.phase === 'completed' && dialog.result && (
                <div className="import-complete">
                  <CheckCircle2 size={34} />
                  <h3>文件已经导入并记录</h3>
                  <p>成功 {dialog.result.success_rows} 行，警告 {dialog.result.warning_rows} 行，错误 {dialog.result.error_rows} 行。</p>
                </div>
              )}
            </div>

            <div className="modal-actions">
              {dialog.phase === 'error' && <button type="button" className="button secondary" onClick={chooseAgain}>重新选择</button>}
              {dialog.phase === 'ready' && <button type="button" className="button primary" disabled={dialog.preview?.importable_rows === 0} onClick={() => void confirmImport()}>确认导入</button>}
              {dialog.phase === 'importing' && <button type="button" className="button primary" disabled>正在导入…</button>}
              {dialog.phase === 'completed' && <button type="button" className="button primary" onClick={closeDialog}>完成</button>}
              {dialog.phase !== 'importing' && dialog.phase !== 'previewing' && dialog.phase !== 'completed' && <button type="button" className="button ghost" onClick={closeDialog}>取消</button>}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
