import { Archive, Edit3, Plus, RotateCcw, UserPlus, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import EmptyState from '../components/EmptyState'
import LoadingState from '../components/LoadingState'
import { ACCOUNT_TYPE_LABELS, ACCOUNT_TYPE_OPTIONS } from '../lib/accounts'
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

export default function AccountsPage() {
  const [members, setMembers] = useState<Member[] | null>(null)
  const [accounts, setAccounts] = useState<Account[] | null>(null)
  const [showArchived, setShowArchived] = useState(false)
  const [newMember, setNewMember] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState<AccountForm>(blankForm())
  const [error, setError] = useState('')

  const load = () => Promise.all([api.get<Member[]>('/members'), api.get<Account[]>('/accounts?include_archived=true')]).then(([memberData, accountData]) => { setMembers(memberData); setAccounts(accountData); if (!form.member_id && memberData[0]) setForm(blankForm(String(memberData[0].id))) }).catch((reason) => setError(errorMessage(reason)))
  useEffect(() => { load() }, [])

  const visibleAccounts = useMemo(() => (accounts ?? []).filter((account) => showArchived || !account.is_archived), [accounts, showArchived])

  const createMember = async () => {
    if (!newMember.trim()) return
    try { await api.post('/members', { name: newMember.trim(), display_name: newMember.trim(), sort_order: members?.length ?? 0 }); setNewMember(''); load() } catch (reason) { setError(errorMessage(reason)) }
  }

  const openCreate = (memberId?: number) => { setEditingId(null); setForm(blankForm(String(memberId ?? members?.[0]?.id ?? ''))); setShowForm(true) }
  const openEdit = (account: Account) => { setEditingId(account.id); setForm({ member_id: String(account.member_id), name: account.name, institution: account.institution ?? '', account_type: account.account_type, credit_limit: centsToInput(account.credit_limit_cents), billing_day: account.billing_day ? String(account.billing_day) : '', include_in_net_worth: account.include_in_net_worth, notes: account.notes ?? '', sort_order: String(account.sort_order) }); setShowForm(true) }

  const saveAccount = async () => {
    try {
      const payload = { member_id: Number(form.member_id), name: form.name.trim(), institution: form.institution.trim() || null, account_type: form.account_type, credit_limit_cents: form.credit_limit ? parseAmountToCents(form.credit_limit) : null, billing_day: form.billing_day ? Number(form.billing_day) : null, include_in_net_worth: form.include_in_net_worth, notes: form.notes.trim() || null, sort_order: Number(form.sort_order || 0) }
      if (!payload.member_id || !payload.name) throw new Error('请选择成员并填写账户名称')
      if (editingId) await api.patch(`/accounts/${editingId}`, payload)
      else await api.post('/accounts', payload)
      setShowForm(false); setEditingId(null); load()
    } catch (reason) { setError(errorMessage(reason)) }
  }

  const toggleArchive = async (account: Account) => {
    const action = account.is_archived ? '恢复' : '归档'
    if (!window.confirm(`${action}账户“${account.name}”？历史快照不会被修改。`)) return
    try { await api.post(`/accounts/${account.id}/${account.is_archived ? 'restore' : 'archive'}`); load() } catch (reason) { setError(errorMessage(reason)) }
  }

  if (!members || !accounts) return <LoadingState />
  return (
    <div className="page">
      <header className="page-header"><div><span className="eyebrow">ACCOUNTS</span><h1>账户管理</h1><p>账户归档后不再进入新盘点，但历史数据会完整保留。</p></div><button className="button primary" onClick={() => openCreate()} disabled={!members.length}><Plus size={18} /> 新建账户</button></header>
      {error && <div className="notice error">{error}</div>}
      <section className="panel member-create"><div><h2>家庭成员</h2><p>先添加成员，再把账户分配给对应的人。</p></div><div className="inline-form"><input placeholder="成员姓名" value={newMember} onChange={(event) => setNewMember(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && createMember()} /><button className="button secondary" onClick={createMember}><UserPlus size={17} /> 添加成员</button></div></section>
      {!members.length ? <EmptyState title="还没有家庭成员" description="添加第一个成员后即可创建微信、银行卡、信用卡和投资账户。" /> : <>
        <div className="filter-row"><label><input type="checkbox" checked={showArchived} onChange={(event) => setShowArchived(event.target.checked)} /> 显示已归档账户</label><span>{visibleAccounts.length} 个账户</span></div>
        {members.map((member) => { const memberAccounts = visibleAccounts.filter((account) => account.member_id === member.id); return <section className="panel accounts-section" key={member.id}><div className="panel-header"><div className="member-heading compact-heading"><div className="member-avatar">{(member.display_name || member.name).slice(0, 1)}</div><div><h2>{member.display_name || member.name}</h2><p>{memberAccounts.length} 个账户</p></div></div><button className="button ghost small" onClick={() => openCreate(member.id)}><Plus size={15} /> 添加账户</button></div>{memberAccounts.length ? <div className="account-card-grid">{memberAccounts.map((account) => <article className={`account-card ${account.is_archived ? 'archived' : ''}`} key={account.id}><div className="account-card-top"><span className="type-tag">{ACCOUNT_TYPE_LABELS[account.account_type]}</span>{account.is_archived && <span className="archive-tag">已归档</span>}</div><h3>{account.name}</h3><p>{account.institution || '未填写机构'}{account.billing_day ? ` · ${account.billing_day} 日还款` : ''}</p>{account.account_type === 'credit_card' && <div className="account-meta"><span>信用额度</span><strong>{formatMoney(account.credit_limit_cents)}</strong></div>}<div className="account-footer"><span>{account.include_in_net_worth ? '计入家庭净资产' : '仅保存，不计入净资产'}</span><div className="row-actions"><button className="icon-button" title="编辑" onClick={() => openEdit(account)}><Edit3 size={16} /></button><button className="icon-button" title={account.is_archived ? '恢复' : '归档'} onClick={() => toggleArchive(account)}>{account.is_archived ? <RotateCcw size={16} /> : <Archive size={16} />}</button></div></div></article>)}</div> : <div className="inline-empty">该成员还没有{showArchived ? '' : '启用中的'}账户。</div>}</section> })}
      </>}

      {showForm && <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && setShowForm(false)}><div className="modal" role="dialog" aria-modal="true" aria-labelledby="account-form-title"><div className="modal-header"><div><h2 id="account-form-title">{editingId ? '编辑账户' : '新建账户'}</h2><p>金额与统计规则会在每期盘点中保存快照。</p></div><button className="icon-button" onClick={() => setShowForm(false)}><X size={20} /></button></div><div className="form-grid"><label>所属成员<select value={form.member_id} onChange={(event) => setForm({ ...form, member_id: event.target.value })}>{members.map((member) => <option key={member.id} value={member.id}>{member.display_name || member.name}</option>)}</select></label><label>账户类型<select value={form.account_type} onChange={(event) => setForm({ ...form, account_type: event.target.value as AccountType })}>{ACCOUNT_TYPE_OPTIONS.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label><label>账户名称<input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="例如：招商银行信用卡" /></label><label>机构名称<input value={form.institution} onChange={(event) => setForm({ ...form, institution: event.target.value })} placeholder="例如：招商银行" /></label>{form.account_type === 'credit_card' && <><label>信用额度<input value={form.credit_limit} onChange={(event) => setForm({ ...form, credit_limit: event.target.value })} placeholder="64000.00" /></label><label>还款日<input type="number" min="1" max="31" value={form.billing_day} onChange={(event) => setForm({ ...form, billing_day: event.target.value })} placeholder="11" /></label></>}<label>排序<input type="number" value={form.sort_order} onChange={(event) => setForm({ ...form, sort_order: event.target.value })} /></label><label className="wide">备注<textarea value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} rows={3} /></label><label className="check-label wide"><input type="checkbox" checked={form.include_in_net_worth} onChange={(event) => setForm({ ...form, include_in_net_worth: event.target.checked })} /> 计入家庭净资产</label></div><div className="modal-actions"><button className="button ghost" onClick={() => setShowForm(false)}>取消</button><button className="button primary" onClick={saveAccount}>{editingId ? '保存修改' : '创建账户'}</button></div></div></div>}
    </div>
  )
}
