import { ChevronRight, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import EmptyState from '../components/EmptyState'
import LoadingState from '../components/LoadingState'
import { api, errorMessage } from '../lib/api'
import { formatMoney } from '../lib/money'
import type { Snapshot } from '../types'

type Metric = 'net_worth_cents' | 'total_assets_cents' | 'total_liabilities_cents'

export default function HistoryPage() {
  const [snapshots, setSnapshots] = useState<Snapshot[] | null>(null)
  const [year, setYear] = useState('all')
  const [metric, setMetric] = useState<Metric>('net_worth_cents')
  const [error, setError] = useState('')

  const load = () => api.get<Snapshot[]>('/snapshots?status=completed').then(setSnapshots).catch((reason) => setError(errorMessage(reason)))
  useEffect(() => {
    void load()
  }, [])

  const years = useMemo(() => [...new Set((snapshots ?? []).map((item) => item.snapshot_date.slice(0, 4)))], [snapshots])
  const filtered = useMemo(() => (snapshots ?? []).filter((item) => year === 'all' || item.snapshot_date.startsWith(year)), [snapshots, year])
  const chartData = [...filtered].reverse()

  const remove = async (snapshot: Snapshot) => {
    if (!window.confirm(`确认删除 ${snapshot.snapshot_date} 的盘点？此操作不会删除账户，但该历史快照将消失。`)) return
    try {
      await api.delete(`/snapshots/${snapshot.id}`)
      load()
    } catch (reason) {
      setError(errorMessage(reason))
    }
  }

  if (!snapshots) return <LoadingState />
  return (
    <div className="page">
      <header className="page-header"><div><span className="eyebrow">HISTORY</span><h1>历史资产</h1><p>每一次完成的盘点都是一张不会被当前账户设置改写的快照。</p></div></header>
      {error && <div className="notice error">{error}</div>}
      {!snapshots.length ? (
        <EmptyState title="还没有历史记录" description="完成第一次盘点后，这里会展示净资产趋势与全部明细。" action={<Link className="button primary" to="/snapshot/new">开始盘点</Link>} />
      ) : (
        <>
          <section className="panel chart-panel history-chart">
            <div className="panel-header">
              <div><h2>家庭资产趋势</h2><p>{year === 'all' ? '全部年份' : `${year} 年`}</p></div>
              <div className="toolbar">
                <select value={year} onChange={(event) => setYear(event.target.value)}><option value="all">全部年份</option>{years.map((item) => <option key={item}>{item}</option>)}</select>
                <div className="segmented">{([['net_worth_cents', '净资产'], ['total_assets_cents', '总资产'], ['total_liabilities_cents', '总负债']] as const).map(([key, label]) => <button key={key} className={metric === key ? 'active' : ''} onClick={() => setMetric(key)}>{label}</button>)}</div>
              </div>
            </div>
            <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><LineChart data={chartData}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e7ebe8" /><XAxis dataKey="snapshot_date" tickLine={false} axisLine={false} /><YAxis tickFormatter={(value) => `${Math.round(Number(value) / 10000) / 10}k`} tickLine={false} axisLine={false} width={48} /><Tooltip formatter={(value) => formatMoney(Number(value))} /><Line dataKey={metric} type="monotone" stroke="#176b51" strokeWidth={2.5} dot={{ r: 3 }} /></LineChart></ResponsiveContainer></div>
          </section>
          <section className="panel table-panel">
            <div className="panel-header"><div><h2>盘点记录</h2><p>共 {filtered.length} 条</p></div></div>
            <div className="table-scroll"><table><thead><tr><th>日期</th><th>总资产</th><th>总负债</th><th>净资产</th><th>环比</th><th aria-label="操作" /></tr></thead><tbody>{filtered.map((item, index) => { const previous = filtered[index + 1]; const change = previous ? item.net_worth_cents - previous.net_worth_cents : null; return <tr key={item.id}><td><Link className="table-link" to={`/snapshots/${item.id}`}>{item.snapshot_date}</Link></td><td>{formatMoney(item.total_assets_cents)}</td><td>{formatMoney(item.total_liabilities_cents)}</td><td className="strong-cell">{formatMoney(item.net_worth_cents)}</td><td className={change !== null && change < 0 ? 'negative' : 'positive'}>{formatMoney(change, true)}</td><td><div className="row-actions"><Link className="icon-button" title="查看并编辑" to={`/snapshots/${item.id}`}><ChevronRight size={17} /></Link><button className="icon-button danger" title="删除" onClick={() => remove(item)}><Trash2 size={16} /></button></div></td></tr> })}</tbody></table></div>
          </section>
        </>
      )}
    </div>
  )
}
