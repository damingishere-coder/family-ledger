import { Archive, Edit3, FolderOpen, Plus, RotateCcw, Search, UserPlus, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import DataActionsPanel from '../components/DataActionsPanel'
import EmptyState from '../components/EmptyState'
import LoadingState from '../components/LoadingState'
import { ACCOUNT_TYPE_LABELS, ACCOUNT_TYPE_OPTIONS, filterAccounts, type AccountFilters } from '../lib/accounts'
import { api, errorMessage } from '../lib/api'
import { centsToInput, formatMoney, parseAmountToCents } from '../lib/money'
import type { Account, AccountType, Member } from '../types'

interface AccountForm {
  member_id: string
  name: string
  institution: string
  account_type: AccountType
  credit_limit: string
  billing_day: string
  include_in_net_worth: boolean
  notes: string
  sort_order: string
}

const blankForm = (memberId = ''): AccountForm => ({ member_id: memberId, name: '', institution: '', account_type: 'wallet', credit_limit: '', billing_day: '', include_in_net_worth: true, notes: '', sort_order: '0' })
const initialFilters: AccountFilters = { memberId: 'all', accountType: 'all', archive: 'active', search: '' }

export default function AccountsPage() {
  const [members, setMembers] = useState<Member[] | null>(null)
  const [accounts, setAccounts] = useState<Account[] | null>(null)
  const [filters, setFilters] = useState<AccountFilters>(initialFilters)
  const [newMember, setNewMember] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState<AccountForm>(blankForm())
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const load = () => Promise.all([api.get<Member[]>('/members'), api.get<Account[]>('/accounts?include_archived=true')]).then(([memberData, accountData]) => { setMembers(memberData); setAccounts(accountData); if (!form.member_id && memberData[0]) setForm(blankForm(String(memberData[0].id))) }).catch((reason) => setError(errorMessage(reason)))
  useEffect(() => { load() }, [])

  const visibleAccounts = useMemo(() => filterAccounts(accounts ?? [], filters), [accounts, filters])
  const visibleMembers = useMemo(
    () => (members ?? []).filter((member) => filters.memberId === 'all' || String(member.id) === filters.memberId),
    [members, filters.memberId],
  )

  const createMember = async () => {
    if (!newMember.trim()) return
    try { await api.post('/members', { name: newMember.trim(), display_name: newMember.trim(), sort_order: members?.length ?? 0 }); setNewMember(''); setMessage('家庭成员已添加。'); load() } catch (reason) { setError(errorMessage(reason)) }
  }

  const openCreate = (memberId?: number) => { setEditingId(null); setForm(blankForm(String(memberId ?? members?.[0]?.id ?? ''))); setShowForm(true) }
  const openEdit = (account: Account) => { setEditingId(account.id); setForm({ member_id: String(account.member_id), name: account.name, institution: account.institution ?? '', account_type: account.account_type, credit_limit: centsToInput(account.credit_limit_cents), billing_day: account.billing_day ? String(account.billing_day) : '', include_in_net_worth: account.include_in_net_worth, notes: account.notes ?? '', sort_order: String(account.sort_order) }); setShowForm(true) }

  const saveAccount = async () => {
    try {
      const payload = { member_id: Number(form.member_id), name: form.name.trim(), institution: form.institution.trim() || null, account_type: form.account_type, credit_limit_cents: form.credit_limit ? parseAmountToCents(form.credit_limit) : null, billing_day: form.billing_day ? Number(form.billing_day) : null, include_in_net_worth: form.include_in_net_worth, notes: form.notes.trim() || null, sort_order: Number(form.sort_order || 0) }
      if (!payload.member_id || !payload.name) throw new Error('请选择成员并填写账户名称')
      if (editingId) await api.patch(`/accounts/${editingId}`, payload)
      else await api.post('/accounts', payload)
      setShowForm(false); setEditingId(null); setMessage(editingId ? '账户修改已保存。' : '账户已创建。'); load()
    } catch (reason) { setError(errorMessage(reason)) }
  }

  const toggleArchive = async (account: Account) => {
    const action = account.is_archived ? '恢复' : '归档'
    if (!window.confirm(`${action}账户“${account.name}”？历史快照不会被修改。`)) return
    try { await api.post(`/accounts/${account.id}/${account.is_archived ? 'restore' : 'archive'}`); setMessage(`账户已${action}。`); load() } catch (reason) { setError(errorMessage(reason)) }
  }

  if (!members || !accounts) return <LoadingState />
  return (
    <div className="page accounts-page">
      <header className="page-header compact-page-header"><div><h1>账户管理</h1><p>管理家庭成员、账户与是否计入家庭净资产。</p></div><button className="button primary" onClick={() => openCreate()} disabled={!members.length}><Plus size={16} /> 新建账户</button></header>
      {message && <div className="notice success">{message}</div>}
      {error && <div className="notice error">{error}</div>}

      <section className="panel member-create"><div><h2>家庭成员</h2><p>新增成员后即可分配账户。</p></div><div className="inline-form"><input placeholder="成员姓名" value={newMember} onChange={(event) => setNewMember(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && void createMember()} /><button className="button secondary" onClick={createMember}><UserPlus size={16} /> 添加成员</button></div></section>

      {!members.length ? <EmptyState title="还没有家庭成员" description="添加第一个成员后即可创建微信、银行卡、信用卡和投资账户。" /> : <>
        <section className="account-toolbar">
          <select aria-label="成员" value={filters.memberId} onChange={(event) => setFilters({ ...filters, memberId: event.target.value })}><option value="all">成员：全部</option>{members.map((member) => <option key={member.id} value={member.id}>{member.display_name || member.name}</option>)}</select>
          <select aria-label="账户类型" value={filters.accountType} onChange={(event) => setFilters({ ...filters, accountType: event.target.value })}><option value="all">类型：全部</option>{ACCOUNT_TYPE_OPTIONS.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select>
          <select aria-label="账户状态" value={filters.archive} onChange={(event) => setFilters({ ...filters, archive: event.target.value as AccountFilters['archive'] })}><option value="active">状态：使用中</option><option value="archived">状态：已归档</option><option value="all">状态：全部</option></select>
          <label className="search-field"><Search size={15} /><input aria-label="搜索账户" placeholder="搜索账户名称、机构或成员" value={filters.search} onChange={(event) => setFilters({ ...filters, search: event.target.value })} /></label>
          <span className="result-count">{visibleAccounts.length} 个账户</span>
        </section>

        <div className="accounts-layout">
          <div className="accounts-main">
            {visibleMembers.map((member) => {
              const memberAccounts = visibleAccounts.filter((account) => account.member_id === member.id)
              const accountGroups = ACCOUNT_TYPE_OPTIONS
                .map(([type, label]) => ({ type, label, accounts: memberAccounts.filter((account) => account.account_type === type) }))
                .filter((group) => group.accounts.length > 0)
              if (!memberAccounts.length && visibleAccounts.length) return null
              return <section className="panel accounts-section" key={member.id}><div className="panel-header account-member-header"><div className="member-heading compact-heading"><div className="member-avatar">{(member.display_name || member.name).slice(0, 1)}</div><div><h2>{member.display_name || member.name}</h2><p>{memberAccounts.length} 个账户 · {accountGroups.length} 类</p></div></div><button className="button ghost small" onClick={() => openCreate(member.id)}><Plus size={14} /> 添加账户</button></div>{memberAccounts.length ? accountGroups.map((group) => <div className="account-type-section" key={group.type}><h3>{group.label}<small>{group.accounts.length} 个</small></h3><div className="table-scroll"><table className="accounts-table"><thead><tr><th>账户名称</th><th>类型</th><th>币种</th><th>计入净资产</th><th>操作</th></tr></thead><tbody>{group.accounts.map((account) => <tr className={account.is_archived ? 'archived-row' : ''} key={account.id}><td><strong>{account.name}</strong><small>{account.institution || '未填写机构'}{account.billing_day ? ` · ${account.billing_day} 日还款` : ''}{account.credit_limit_cents !== null ? ` · 额度 ${formatMoney(account.credit_limit_cents)}` : ''}</small></td><td><span className="type-tag">{ACCOUNT_TYPE_LABELS[account.account_type]}</span>{account.is_archived && <span className="archive-tag">已归档</span>}</td><td>CNY</td><td><span className={account.include_in_net_worth ? 'include-badge' : 'exclude-badge'}>{account.include_in_net_worth ? '计入净资产' : '不计入'}</span></td><td><div className="table-text-actions"><button onClick={() => openEdit(account)}><Edit3 size={13} /> 编辑</button><button onClick={() => toggleArchive(account)}>{account.is_archived ? <RotateCcw size={13} /> : <Archive size={13} />}{account.is_archived ? '恢复' : '归档'}</button></div></td></tr>)}</tbody></table></div></div>) : <div className="inline-empty">没有符合当前筛选条件的账户。</div>}</section>
            })}
          </div>
          <aside className="accounts-aside">
            <DataActionsPanel compact onChanged={load} onMessage={(value) => { setError(''); setMessage(value) }} onError={(value) => { setMessage(''); setError(value) }} />
            <div className="panel local-path-card"><span className="data-action-icon"><FolderOpen size={16} /></span><div><strong>本地数据位置</strong><p>./data/family_finance.db</p></div></div>
          </aside>
        </div>
      </>}

      {showForm && <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && setShowForm(false)}><div className="modal" role="dialog" aria-modal="true" aria-labelledby="account-form-title"><div className="modal-header"><div><h2 id="account-form-title">{editingId ? '编辑账户' : '新建账户'}</h2><p>金额与统计规则会在每期盘点中保存快照。</p></div><button className="icon-button" aria-label="关闭" onClick={() => setShowForm(false)}><X size={19} /></button></div><div className="form-grid"><label>所属成员<select value={form.member_id} onChange={(event) => setForm({ ...form, member_id: event.target.value })}>{members.map((member) => <option key={member.id} value={member.id}>{member.display_name || member.name}</option>)}</select></label><label>账户类型<select value={form.account_type} onChange={(event) => setForm({ ...form, account_type: event.target.value as AccountType })}>{ACCOUNT_TYPE_OPTIONS.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label><label>账户名称<input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="例如：招商银行信用卡" /></label><label>机构名称<input value={form.institution} onChange={(event) => setForm({ ...form, institution: event.target.value })} placeholder="例如：招商银行" /></label>{form.account_type === 'credit_card' && <><label>信用额度<input value={form.credit_limit} onChange={(event) => setForm({ ...form, credit_limit: event.target.value })} placeholder="64000.00" /></label><label>还款日<input type="number" min="1" max="31" value={form.billing_day} onChange={(event) => setForm({ ...form, billing_day: event.target.value })} placeholder="11" /></label></>}<label>排序<input type="number" value={form.sort_order} onChange={(event) => setForm({ ...form, sort_order: event.target.value })} /></label><label className="wide">备注<textarea value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} rows={3} /></label><label className="check-label wide"><input type="checkbox" checked={form.include_in_net_worth} onChange={(event) => setForm({ ...form, include_in_net_worth: event.target.checked })} /> 计入家庭净资产</label></div><div className="modal-actions"><button className="button ghost" onClick={() => setShowForm(false)}>取消</button><button className="button primary" onClick={saveAccount}>{editingId ? '保存修改' : '创建账户'}</button></div></div></div>}
    </div>
  )
}
