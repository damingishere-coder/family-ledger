import { ArrowRight, CircleDollarSign, Plus, TrendingDown, TrendingUp } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import EmptyState from '../components/EmptyState'
import LoadingState from '../components/LoadingState'
import { api, errorMessage } from '../lib/api'
import { formatMoney } from '../lib/money'
import type { DashboardData } from '../types'

type Metric = 'net_worth_cents' | 'total_assets_cents' | 'total_liabilities_cents'

const metricLabels: Record<Metric, string> = {
  net_worth_cents: '净资产',
  total_assets_cents: '总资产',
  total_liabilities_cents: '总负债',
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState('')
  const [metric, setMetric] = useState<Metric>('net_worth_cents')

  useEffect(() => {
    api.get<DashboardData>('/dashboard').then(setData).catch((reason) => setError(errorMessage(reason)))
  }, [])

  const maxComposition = useMemo(
    () => Math.max(...(data?.composition.map((item) => Math.abs(item.amount_cents)) ?? [1]), 1),
    [data],
  )

  if (error) return <div className="notice error">{error}</div>
  if (!data) return <LoadingState label="正在读取家庭资产…" />

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <span className="eyebrow">FAMILY FINANCE</span>
          <h1>家庭资产概览</h1>
          <p>{data.snapshot_date ? `最近盘点于 ${data.snapshot_date}` : '先建立账户，再完成第一次家庭资产盘点。'}</p>
        </div>
        <Link className="button primary" to="/snapshot/new">
          <Plus size={18} /> 新建本期盘点
        </Link>
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
          <section className="kpi-grid">
            <article className="kpi-card featured">
              <div className="kpi-label"><CircleDollarSign size={18} /> 家庭净资产</div>
              <strong>{formatMoney(data.current.net_worth_cents)}</strong>
              <span className={data.change_from_previous_cents && data.change_from_previous_cents < 0 ? 'negative' : 'positive'}>
                {data.change_from_previous_cents === null ? '首期数据' : (
                  <>{data.change_from_previous_cents < 0 ? <TrendingDown size={15} /> : <TrendingUp size={15} />} 较上期 {formatMoney(data.change_from_previous_cents, true)}</>
                )}
              </span>
            </article>
            <article className="kpi-card">
              <div className="kpi-label">家庭总资产</div>
              <strong>{formatMoney(data.current.total_assets_cents)}</strong>
              <span>计入净资产的资产账户</span>
            </article>
            <article className="kpi-card">
              <div className="kpi-label">家庭总负债</div>
              <strong>{formatMoney(data.current.total_liabilities_cents)}</strong>
              <span>信用卡与其他负债</span>
            </article>
            <article className="kpi-card">
              <div className="kpi-label">投资资产</div>
              <strong>{formatMoney(data.current.investment_assets_cents)}</strong>
              <span>投资账户合计</span>
            </article>
          </section>

          <section className="dashboard-grid">
            <article className="panel chart-panel">
              <div className="panel-header">
                <div><h2>资产趋势</h2><p>每次已完成盘点形成一个可靠快照</p></div>
                <div className="segmented">
                  {(Object.keys(metricLabels) as Metric[]).map((key) => (
                    <button className={metric === key ? 'active' : ''} onClick={() => setMetric(key)} key={key}>{metricLabels[key]}</button>
                  ))}
                </div>
              </div>
              <div className="chart-wrap">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={data.trend} margin={{ top: 12, right: 12, left: 4, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e7ebe8" />
                    <XAxis dataKey="date" tickFormatter={(value) => String(value).slice(0, 7).replace('-', '/')} tickLine={false} axisLine={false} />
                    <YAxis tickFormatter={(value) => `${Math.round(Number(value) / 10000) / 10}k`} tickLine={false} axisLine={false} width={48} />
                    <Tooltip formatter={(value) => formatMoney(Number(value))} labelFormatter={(value) => `盘点日期 ${value}`} />
                    <Line type="monotone" dataKey={metric} name={metricLabels[metric]} stroke="#176b51" strokeWidth={2.5} dot={{ r: 3, fill: '#176b51' }} activeDot={{ r: 5 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </article>

            <article className="panel composition-panel">
              <div className="panel-header"><div><h2>资产构成</h2><p>最近一期计入净资产的资产</p></div></div>
              <div className="composition-list">
                {data.composition.length ? data.composition.map((item) => (
                  <div className="composition-row" key={item.name}>
                    <div><span>{item.name}</span><strong>{formatMoney(item.amount_cents)}</strong></div>
                    <div className="bar"><span style={{ width: `${Math.max(4, Math.abs(item.amount_cents) / maxComposition * 100)}%` }} /></div>
                  </div>
                )) : <p className="muted">暂无计入统计的资产</p>}
              </div>
            </article>
          </section>

          <section className="dashboard-grid lower">
            <article className="panel">
              <div className="panel-header"><div><h2>家庭成员</h2><p>按最近一期盘点汇总</p></div></div>
              <div className="member-grid">
                {data.members.map((member) => (
                  <div className="member-card" key={member.name}>
                    <div className="member-avatar">{member.name.slice(0, 1)}</div>
                    <div><h3>{member.name}</h3><strong>{formatMoney(member.net_worth_cents)}</strong></div>
                    <dl><div><dt>资产</dt><dd>{formatMoney(member.assets_cents)}</dd></div><div><dt>负债</dt><dd>{formatMoney(member.liabilities_cents)}</dd></div></dl>
                  </div>
                ))}
              </div>
            </article>

            <article className="panel">
              <div className="panel-header"><div><h2>最近盘点</h2><p>最近 {data.recent.length} 期</p></div><Link className="text-link" to="/history">查看全部 <ArrowRight size={15} /></Link></div>
              <div className="compact-list">
                {data.recent.slice(0, 5).map((item) => (
                  <Link to={`/snapshots/${item.id}`} key={item.id}>
                    <span>{item.snapshot_date}</span>
                    <strong>{formatMoney(item.net_worth_cents)}</strong>
                    <ArrowRight size={15} />
                  </Link>
                ))}
              </div>
            </article>
          </section>
        </>
      )}
    </div>
  )
}
