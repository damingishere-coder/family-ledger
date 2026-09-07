import { ArrowRight, Landmark, Plus, TrendingDown, TrendingUp, WalletCards } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import EmptyState from '../components/EmptyState'
import LoadingState from '../components/LoadingState'
import { api, errorMessage } from '../lib/api'
import { formatSnapshotMonth, formatSnapshotMonthShort } from '../lib/month'
import { currentMonthLocal } from '../lib/month'
import { formatMoney, formatChartMoney } from '../lib/money'
import type { DashboardData, Snapshot } from '../types'

type Metric = 'net_worth_cents' | 'total_assets_cents' | 'total_liabilities_cents'

const metricLabels: Record<Metric, string> = {
  net_worth_cents: '净资产',
  total_assets_cents: '总资产',
  total_liabilities_cents: '总负债',
}

const compositionColors = ['#0a63f6', '#38a3ff', '#22b07d', '#f59e42', '#8b6cf6', '#8aa0be']

function percentageChange(current: number, previous: number | undefined) {
  if (previous === undefined || previous === 0) return null
  return (current - previous) / Math.abs(previous) * 100
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState('')
  const [metric, setMetric] = useState<Metric>('net_worth_cents')
  const [draft, setDraft] = useState<Snapshot | null>(null)
  const [switching, setSwitching] = useState(false)

  useEffect(() => {
    Promise.all([api.get<DashboardData>('/dashboard'), api.get<Snapshot | null>('/snapshots/active-draft')])
      .then(([dashboard, activeDraft]) => { setData(dashboard); setDraft(activeDraft) })
      .catch((reason) => setError(errorMessage(reason)))
  }, [])

  const previous = data?.trend.at(-2)
  const composition = useMemo(
    () => (data?.composition ?? []).map((item) => ({ ...item, chartValue: item.amount_cents })),
    [data?.composition],
  )
  const compositionTotal = composition.reduce((total, item) => total + item.chartValue, 0)

  if (error) return <div className="page"><div className="notice error">{error}</div></div>
  if (!data) return <LoadingState label="正在读取家庭资产…" />
  const completed = data.recent.find(s => s.snapshot_date.startsWith(currentMonthLocal()))

  return (
    <div className="page dashboard-page">
      <header className="page-header compact-page-header">
        <div>
          <h1>概览</h1>
          <p>{data.snapshot_date ? `${formatSnapshotMonth(data.snapshot_date)} · ${data.source ? '历史导入' : '手工录入'} · ${data.current?.total_entries ?? 0} 个账户` : '建立账户后即可开始第一次家庭资产盘点。'}</p>
        </div>
        <div className="button-row">
        {data.periods?.length ? <select aria-label="查看盘点月份" value={data.snapshot_id} disabled={switching} onChange={async event => {
          setSwitching(true)
          try { setData(await api.get<DashboardData>(`/dashboard?snapshot_id=${event.target.value}`)) }
          catch (reason) { setError(errorMessage(reason)) }
          finally { setSwitching(false) }
        }}>{data.periods.map(period => <option key={period.id} value={period.id}>{formatSnapshotMonth(period.date)}</option>)}</select> : null}
        <Link className="button primary" to={draft ? '/snapshot/new' : completed ? `/snapshots/${completed.id}` : '/snapshot/new'}>
          <Plus size={16} /> {draft ? '继续草稿' : completed ? '查看本月盘点' : '开始本月盘点'}
        </Link>
        </div>
      </header>

      {!data.current ? (
        <EmptyState
          title="还没有已完成的盘点"
          description="创建家庭成员和账户后，录入第一次余额，净资产趋势会从这里开始。"
          action={
            <div className="button-row centered">
              <Link className="button secondary" to="/accounts">管理成员和账户</Link>
              <Link className="button primary" to="/snapshot/new">开始第一次盘点</Link>
            </div>
          }
        />
      ) : (
        <>
          {data.previous_entry_count != null && data.current.total_entries < data.previous_entry_count && <div className="notice warning">本期记录 {data.current.total_entries} 个账户，上期为 {data.previous_entry_count} 个。这里只统计本期明细，不会自动沿用未录入账户的上期余额。</div>}
          <section className="kpi-grid">
            {[
              { label: '家庭净资产', value: data.current.net_worth_cents, previous: previous?.net_worth_cents, icon: WalletCards },
              { label: '总资产', value: data.current.total_assets_cents, previous: previous?.total_assets_cents, icon: Landmark },
              { label: '总负债', value: data.current.total_liabilities_cents, previous: previous?.total_liabilities_cents, icon: WalletCards },
              { label: '投资资产', value: data.current.investment_assets_cents, previous: undefined, icon: TrendingUp },
            ].map(({ label, value, previous: previousValue, icon: Icon }) => {
              const rate = percentageChange(value, previousValue)
              const delta = previousValue === undefined ? null : value - previousValue
              return (
                <article className="kpi-card" key={label}>
                  <div className="kpi-label"><Icon size={16} /> {label}</div>
                  <strong>{formatMoney(value)}</strong>
                  {rate === null ? (
                    <span>{label === '投资资产' ? '投资账户合计' : delta !== null ? `较上期 ${formatMoney(delta, true)}` : '首期数据'}</span>
                  ) : (
                    <span className={delta !== null && (label === '总负债' ? delta > 0 : delta < 0) ? 'negative' : 'positive'}>
                      {delta !== null && delta < 0 ? <TrendingDown size={14} /> : <TrendingUp size={14} />}
                      较上期 {rate > 0 ? '+' : ''}{rate.toFixed(2)}%
                    </span>
                  )}
                </article>
              )
            })}
          </section>

          <section className="member-overview" aria-label="成员资产汇总">
            {data.members.map(member => <Link className="panel member-overview-card" to={`/snapshots/${data.snapshot_id}`} key={member.name}>
              <h2>{member.name}</h2><span>净资产</span><strong>{formatMoney(member.net_worth_cents)}</strong>
              <p>资产 {formatMoney(member.assets_cents)} · 负债 {formatMoney(member.liabilities_cents)}</p><span className="text-link">查看账户明细 <ArrowRight size={14} /></span>
            </Link>)}
          </section>

          <section className="dashboard-grid">
            <article className="panel chart-panel">
              <div className="panel-header">
                <div><h2>净资产趋势</h2><p>每次完成盘点后自动更新</p></div>
                <div className="segmented">
                  {(Object.keys(metricLabels) as Metric[]).map((key) => (
                    <button type="button" className={metric === key ? 'active' : ''} onClick={() => setMetric(key)} key={key}>{metricLabels[key]}</button>
                  ))}
                </div>
              </div>
              <div className="chart-wrap">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={data.trend} margin={{ top: 10, right: 18, left: 4, bottom: 2 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e8eef7" />
                    <XAxis dataKey="date" tickFormatter={(value) => formatSnapshotMonthShort(String(value))} tickLine={false} axisLine={false} />
                    <YAxis tickFormatter={(value) => formatChartMoney(Number(value))} tickLine={false} axisLine={false} width={52} />
                    <Tooltip formatter={(value) => formatMoney(Number(value))} labelFormatter={(value) => `盘点月份 ${formatSnapshotMonth(String(value))}`} />
                    <Line type="monotone" dataKey={metric} name={metricLabels[metric]} stroke="#0a63f6" strokeWidth={2.5} dot={{ r: 3, fill: '#0a63f6', strokeWidth: 0 }} activeDot={{ r: 5 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </article>

            <article className="panel composition-panel">
              <div className="panel-header"><div><h2>资产构成</h2><p>所选月份计入净资产的资产</p></div></div>
              {composition.some(item => item.amount_cents < 0) ? <div className="signed-composition"><p className="muted">存在负余额，按实际金额展示</p>{composition.map(item => <div key={item.name}><span>{item.name}</span><strong>{formatMoney(item.amount_cents)}</strong></div>)}</div> : composition.length && compositionTotal ? (
                <div className="composition-content">
                  <div className="donut-wrap">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={composition} dataKey="chartValue" nameKey="name" innerRadius="58%" outerRadius="82%" paddingAngle={2} stroke="none">
                          {composition.map((item, index) => <Cell key={item.name} fill={compositionColors[index % compositionColors.length]} />)}
                        </Pie>
                        <Tooltip formatter={(value) => formatMoney(Number(value))} />
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="donut-center"><strong>{composition.length}</strong><span>类资产</span></div>
                  </div>
                  <div className="composition-legend">
                    {composition.map((item, index) => (
                      <div key={item.name}>
                        <span className="legend-dot" style={{ background: compositionColors[index % compositionColors.length] }} />
                        <span>{item.name}</span>
                        <strong>{(item.chartValue / compositionTotal * 100).toFixed(1)}%</strong>
                      </div>
                    ))}
                  </div>
                </div>
              ) : <div className="inline-empty">暂无计入统计的资产。</div>}
            </article>
          </section>

          <section className="panel table-panel recent-snapshots">
            <div className="panel-header">
              <div><h2>最近盘点</h2><p>最近 {Math.min(data.recent.length, 6)} 期家庭资产记录</p></div>
              <Link className="text-link" to="/history">查看全部 <ArrowRight size={14} /></Link>
            </div>
            <div className="table-scroll">
              <table>
                <thead><tr><th>月份</th><th>总资产</th><th>总负债</th><th>净资产</th><th>环比</th><th aria-label="操作" /></tr></thead>
                <tbody>{data.recent.slice(0, 6).map((item, index) => {
                  const older = data.recent[index + 1]
                  const change = older ? item.net_worth_cents - older.net_worth_cents : null
                  return <tr key={item.id}><td>{formatSnapshotMonth(item.snapshot_date)}</td><td>{formatMoney(item.total_assets_cents)}</td><td>{formatMoney(item.total_liabilities_cents)}</td><td className="strong-cell">{formatMoney(item.net_worth_cents)}</td><td className={change !== null && change < 0 ? 'negative' : 'positive'}>{formatMoney(change, true)}</td><td><Link className="table-action" to={`/snapshots/${item.id}`}>查看</Link></td></tr>
                })}</tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  )
}
