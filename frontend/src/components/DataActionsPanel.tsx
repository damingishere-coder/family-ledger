import { DatabaseBackup, Download, FileSpreadsheet, Upload } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, errorMessage } from '../lib/api'

interface Props { compact?: boolean; onMessage?: (message: string) => void;
  onError?: (message: string) => void; onChanged?: () => void | Promise<void> }

export default function DataActionsPanel({ onMessage, onError }: Props) {
  const [busy, setBusy] = useState(false)
  const backup = async () => {
    setBusy(true)
    try { const result = await api.post<{ filename: string }>('/backup'); onMessage?.(`备份已保存：${result.filename}`) }
    catch (reason) { onError?.(errorMessage(reason)) }
    finally { setBusy(false) }
  }
  return <section className="panel data-actions-panel">
    <div className="panel-header"><div><h2>导入与导出</h2><p>核对历史表格，或导出一份自己的数据</p></div></div>
    <div className="data-action-list">
      <Link className="data-action import-entry-link" to="/data/import"><span className="data-action-icon"><Upload size={20} /></span><span><strong>导入并核对历史表格</strong><small>一起选择 Excel 和 Markdown，逐项核对成员与类型</small></span></Link>
      <a className="data-action" href="/api/export/excel"><span className="data-action-icon"><FileSpreadsheet size={20} /></span><span><strong>导出 Excel</strong><small>查看或整理全部账户明细</small></span></a>
      <a className="data-action" href="/api/export/csv"><span className="data-action-icon"><Download size={20} /></span><span><strong>导出 CSV</strong><small>用于其他表格软件</small></span></a>
      <a className="data-action" href="/api/export/json"><span className="data-action-icon"><Download size={20} /></span><span><strong>下载完整备份</strong><small>包含成员、账户、历史和导入核对记录，可用于恢复</small></span></a>
      <button className="data-action" disabled={busy} onClick={() => void backup()}><span className="data-action-icon"><DatabaseBackup size={20} /></span><span><strong>{busy ? '正在备份…' : '在本机创建备份'}</strong><small>保存到本机备份文件夹</small></span></button>
    </div>
  </section>
}
