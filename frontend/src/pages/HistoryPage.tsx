import { BarChart3, ChevronRight, List, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import EmptyState from '../components/EmptyState'
import LoadingState from '../components/LoadingState'
import { api, errorMessage } from '../lib/api'
import { formatSnapshotMonth, formatSnapshotMonthShort } from '../lib/month'
import { formatMoney } from '../lib/money'
import { compareSnapshots } from '../lib/snapshots'
import type { Snapshot } from '../types'

type Metric = 'net_worth_cents' | 'total_assets_cents' | 'total_liabilities_cents'
type HistoryView = 'chart' | 'table'

export default function HistoryPage() {
  const [snapshots, setSnapshots] = useState<Snapshot[] | null>(null)
  const [year, setYear] = useState('all')
  const [metric, setMetric] = useState<Metric>('net_worth_cents')
  const [view, setView] = useState<HistoryView>('chart')
  const [error, setError] = useState('')

  const load = () => api.get<Snapshot[]>('/snapshots?status=completed').then(setSnapshots).catch((reason) => setError(errorMessage(reason)))
  useEffect(() => {
    void load()
  }, [])

  const years = useMemo(() => [...new Set((snapshots ?? []).map((item) => item.snapshot_date.slice(0, 4)))].sort().reverse(), [snapshots])
  const filtered = useMemo(
    () => (snapshots ?? []).filter((item) => year === 'all' || item.snapshot_date.startsWith(year)).sort((left, right) => right.snapshot_date.localeCompare(left.snapshot_date)),
    [snapshots, year],
  )
  const chartData = [...filtered].reverse()
  const comparison = compareSnapshots(filtered[0], filtered[1])

  const remove = async (snapshot: Snapshot) => {
    if (!window.confirm(`确认删除 ${formatSnapshotMonth(snapshot.snapshot_date)}的盘点？此操作不会删除账户，但该历史快照将消失。`)) return
    try {
      await api.delete(`/snapshots/${snapshot.id}`)
      load()
    } catch (reason) {
      setError(errorMessage(reason))
    }
  }

  if (!snapshots) return <LoadingState />
  return (
    <div className="page history-page">
      <header className="page-header compact-page-header"><div><h1>历史记录</h1><p>查看家庭资产的长期变化与每期可靠快照。</p></div></header>
      {error && <div className="notice error">{error}</div>}
      {!snapshots.length ? (
        <EmptyState title="还没有历史记录" description="完成第一次盘点后，这里会展示净资产趋势与全部明细。" action={<Link className="button primary" to="/snapshot/new">开始盘点</Link>} />
      ) : (
        <>
          <div className="history-toolbar">
            <div className="year-tabs">
              <button type="button" className={year === 'all' ? 'active' : ''} onClick={() => setYear('all')}>全部</button>
              {years.map((item) => <button type="button" className={year === item ? 'active' : ''} onClick={() => setYear(item)} key={item}>{item}</button>)}
            </div>
            <div className="view-switch">
              <button type="button" className={view === 'chart' ? 'active' : ''} onClick={() => setView('chart')}><BarChart3 size={14} /> 图表</button>
              <button type="button" className={view === 'table' ? 'active' : ''} onClick={() => setView('table')}><List size={14} /> 表格</button>
            </div>
          </div>

          {view === 'chart' && (
            <section className="history-overview-grid">
              <article className="panel chart-panel history-chart">
                <div className="panel-header">
                  <div><h2>家庭资产趋势</h2><p>{year === 'all' ? '全部年份' : `${year} 年`}</p></div>
                  <div className="segmented">{([['net_worth_cents', '净资产'], ['total_assets_cents', '总资产'], ['total_liabilities_cents', '总负债']] as const).map(([key, label]) => <button type="button" key={key} className={metric === key ? 'active' : ''} onClick={() => setMetric(key)}>{label}</button>)}</div>
                </div>
                <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><LineChart data={chartData} margin={{ top: 10, right: 16, left: 4, bottom: 2 }}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e8eef7" /><XAxis dataKey="snapshot_date" tickFormatter={(value) => formatSnapshotMonthShort(String(value))} tickLine={false} axisLine={false} /><YAxis tickFormatter={(value) => `${Math.round(Number(value) / 10_000)}万`} tickLine={false} axisLine={false} width={52} /><Tooltip formatter={(value) => formatMoney(Number(value))} labelFormatter={(value) => formatSnapshotMonth(String(value))} /><Line dataKey={metric} type="monotone" stroke="#0a63f6" strokeWidth={2.5} dot={{ r: 3, fill: '#0a63f6', strokeWidth: 0 }} activeDot={{ r: 5 }} /></LineChart></ResponsiveContainer></div>
              </article>
              <article className="panel comparison-panel">
                <div className="panel-header"><div><h2>与上期比较</h2><p>{filtered[0] && filtered[1] ? `${formatSnapshotMonthShort(filtered[1].snapshot_date)} → ${formatSnapshotMonthShort(filtered[0].snapshot_date)}` : '暂无上期数据'}</p></div></div>
                <dl className="comparison-list">
                  <div><dt>净资产</dt><dd className={comparison.net_worth_cents !== null && comparison.net_worth_cents < 0 ? 'negative' : 'positive'}>{formatMoney(comparison.net_worth_cents, true)}</dd></div>
                  <div><dt>总资产</dt><dd className={comparison.assets_cents !== null && comparison.assets_cents < 0 ? 'negative' : 'positive'}>{formatMoney(comparison.assets_cents, true)}</dd></div>
                  <div><dt>总负债</dt><dd className={comparison.liabilities_cents !== null && comparison.liabilities_cents > 0 ? 'negative' : 'positive'}>{formatMoney(comparison.liabilities_cents, true)}</dd></div>
                </dl>
              </article>
            </section>
          )}

          <section className={`panel table-panel history-table ${view === 'table' ? 'table-focus' : ''}`}>
            <div className="panel-header"><div><h2>盘点记录</h2><p>共 {filtered.length} 条</p></div></div>
            <div className="table-scroll"><table><thead><tr><th>月份</th><th>总资产</th><th>总负债</th><th>净资产</th><th>环比</th><th aria-label="操作" /></tr></thead><tbody>{filtered.map((item, index) => { const previous = filtered[index + 1]; const change = previous ? item.net_worth_cents - previous.net_worth_cents : null; return <tr key={item.id}><td><Link className="table-link" to={`/snapshots/${item.id}`}>{formatSnapshotMonth(item.snapshot_date)}</Link></td><td>{formatMoney(item.total_assets_cents)}</td><td>{formatMoney(item.total_liabilities_cents)}</td><td className="strong-cell">{formatMoney(item.net_worth_cents)}</td><td className={change !== null && change < 0 ? 'negative' : 'positive'}>{formatMoney(change, true)}</td><td><div className="row-actions"><Link className="icon-button" title="查看并编辑" to={`/snapshots/${item.id}`}><ChevronRight size={16} /></Link><button className="icon-button danger" title="删除" onClick={() => remove(item)}><Trash2 size={15} /></button></div></td></tr> })}</tbody></table></div>
          </section>
        </>
      )}
    </div>
  )
}
