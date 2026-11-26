import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowDown, ArrowUp, Check, Plus, Search, UserPlus, Users, X } from 'lucide-react'
import { api, useApi } from '../../api'
import { Alert, Badge, Card, Empty, ErrorState, Field, Loading, Modal, PageHeader, fmt, prettyDate, todayIso, useAction, ViewAll } from '../../components/ui'

export const PASS_TONE = { active: 'green', expiring_soon: 'amber', expired: 'red', suspended: 'purple', none: '', upcoming: 'blue' }
export const PassBadge = ({ p }) => <Badge tone={PASS_TONE[p.status]}>{p.label}</Badge>

export function RemainingBar({ p }) {
  if (!p.has_pass) return <span className="faint small">—</span>
  return (
    <div style={{ minWidth: 110 }}>
      <div className="small strong">{p.remaining_days} <span className="faint" style={{ fontWeight: 400 }}>/ {p.total_days} days</span></div>
      <div className={`pass-bar ${p.color}`} style={{ height: 6, marginTop: 4 }}><i style={{ width: `${p.progress_pct}%` }} /></div>
    </div>
  )
}

const CHIPS = [['', 'All'], ['active', 'Active'], ['expiring_soon', 'Expiring soon'], ['expired', 'Expired'], ['suspended', 'Suspended'], ['none', 'No pass']]
const COLS = [['name', 'Student'], ['student_code', 'Student ID'], [null, 'Contact'], [null, 'Pass type'], ['purchase_date', 'Purchased'],
  ['expiry_date', 'Expiry'], ['remaining_days', 'Remaining'], ['status', 'Status']]

function AddStudent({ onClose, onDone }) {
  const [f, setF] = useState({ name: '', email: '', student_code: '', phone: '', department: '', year_of_study: '', password: '', pass_type: 'monthly', start_date: todayIso() })
  const [run, busy] = useAction()
  const [made, setMade] = useState(null)
  const set = k => e => setF({ ...f, [k]: e.target.value })
  async function save() {
    const body = { ...f, year_of_study: f.year_of_study ? Number(f.year_of_study) : null, password: f.password || null,
      phone: f.phone || null, department: f.department || null, pass_type: f.pass_type || null, start_date: f.pass_type ? f.start_date : null }
    const r = await run(() => api('/admin/students', { method: 'POST', body }), 'Student added')
    if (r) { setMade(r); onDone() }
  }
  return (
    <Modal open title={made ? 'Student added' : 'Add student'} onClose={onClose} width={620}
      footer={made ? <button className="btn primary" onClick={onClose}>Done</button>
        : <><button className="btn ghost" onClick={onClose}>Cancel</button><button className="btn primary" disabled={busy || !f.name || !f.email || !f.student_code} onClick={save}>Add student</button></>}>
      {made ? (
        <div className="stack">
          <Alert tone="success"><b>{made.student.name}</b> ({made.student.student_code}) can now sign in with their email or student ID.</Alert>
          {made.temporary_password && <div className="formula">Temporary password: <b>{made.temporary_password}</b><div className="tiny faint mt-4">Share it privately. It is shown only once; the student should change it under Profile.</div></div>}
        </div>
      ) : (
        <div className="form-grid">
          <Field label="Full name" className="span-all"><input className="input" value={f.name} onChange={set('name')} autoFocus /></Field>
          <Field label="Email"><input className="input" type="email" value={f.email} onChange={set('email')} /></Field>
          <Field label="Student ID"><input className="input" value={f.student_code} onChange={set('student_code')} placeholder="e.g. STU2030" /></Field>
          <Field label="Contact number"><input className="input" value={f.phone} onChange={set('phone')} /></Field>
          <Field label="Department"><input className="input" value={f.department} onChange={set('department')} /></Field>
          <Field label="Password" hint="Leave blank to generate a temporary password"><input className="input" type="text" value={f.password} onChange={set('password')} placeholder="min. 8 characters" /></Field>
          <Field label="Year"><select className="select" value={f.year_of_study} onChange={set('year_of_study')}><option value="">—</option>{[1, 2, 3, 4, 5].map(y => <option key={y} value={y}>Year {y}</option>)}</select></Field>
          <Field label="Mess pass"><select className="select" value={f.pass_type} onChange={set('pass_type')}><option value="monthly">Monthly (30 days)</option><option value="six_month">Six-month (180 days)</option><option value="">No pass yet</option></select></Field>
          {f.pass_type && <Field label="Pass start date"><input className="input" type="date" value={f.start_date} onChange={set('start_date')} /></Field>}
        </div>
      )}
    </Modal>
  )
}

function Renewals({ onChange }) {
  const { data, reload } = useApi('/admin/renewals')
  const [run, busy] = useAction()
  if (!data?.length) return null
  const act = async (r, action) => {
    if (action === 'approve' && !window.confirm(`Approve a ${r.pass_label} pass for ${r.name}? It starts after their current pass (or today).`)) return
    if (await run(() => api(`/admin/renewals/${r.id}`, { method: 'POST', body: { action } }), action === 'approve' ? 'Pass renewed' : 'Request declined')) { reload(true); onChange() }
  }
  return (
    <Card viewAll title={`Renewal requests (${data.length})`} subtitle="Students who asked to renew their mess pass">
      <div className="list">{data.map(r => (
        <div className="list-item" key={r.id}>
          <div><div className="strong small">{r.name} · {r.student_code}</div><div className="tiny faint">{r.pass_label} pass · requested {prettyDate(r.created_at)}</div></div>
          <div className="row"><button className="btn sm primary" disabled={busy} onClick={() => act(r, 'approve')}><Check />Approve</button><button className="btn sm ghost" disabled={busy} onClick={() => act(r, 'reject')}><X />Decline</button></div>
        </div>))}</div>
    </Card>
  )
}

export default function Students() {
  const nav = useNavigate()
  const [q, setQ] = useState('')
  const [f, setF] = useState({ q: '', status: new URLSearchParams(window.location.search).get('status') || '', pass_type: '', sort: 'name', direction: 'asc', page: 1 })
  useEffect(() => { const t = setTimeout(() => setF(x => ({ ...x, q, page: 1 })), 300); return () => clearTimeout(t) }, [q])
  const { data, error, loading, reload } = useApi('/admin/students', { ...f, size: 200 })
  const [adding, setAdding] = useState(false)
  const pages = data ? Math.max(1, Math.ceil(data.total / data.size)) : 1
  const sortBy = k => k && setF({ ...f, sort: k, direction: f.sort === k && f.direction === 'asc' ? 'desc' : 'asc' })
  const c = data?.counts || {}

  return (
    <div className="stack">
      <PageHeader title="Student Management" subtitle="Registered students, mess passes and validity in one place."
        actions={<button className="btn primary" onClick={() => setAdding(true)}><UserPlus />Add student</button>} />
      <Renewals onChange={() => reload(true)} />
      <div className="card card-pad stack" style={{ gap: 14 }}>
        <div className="between wrap">
          <div className="filter-chips">{CHIPS.map(([k, l]) => (
            <button key={k} className={f.status === k ? 'on' : ''} onClick={() => setF({ ...f, status: k, page: 1 })}>{l}<b>{k ? c[k] || 0 : Object.values(c).reduce((a, b) => a + b, 0)}</b></button>
          ))}</div>
          <div className="row wrap">
            <div className="search" style={{ maxWidth: 260 }}><Search /><input placeholder="Search name or student ID" value={q} onChange={e => setQ(e.target.value)} aria-label="Search students" /></div>
            <select className="select sm" style={{ width: 150 }} value={f.pass_type} onChange={e => setF({ ...f, pass_type: e.target.value, page: 1 })} aria-label="Pass type">
              <option value="">All pass types</option><option value="monthly">Monthly</option><option value="six_month">Six-month</option></select>
          </div>
        </div>
        {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Loading rows={8} /> : !data.items.length ? (
          <Empty icon={Users} title="No students match">Try another filter or add a student.</Empty>
        ) : <>
          <ViewAll limit={10} noun="students"><div className="table-wrap" style={{ margin: '0 -22px' }}>
            <table className="table">
              <thead><tr>{COLS.map(([k, l]) => (
                <th key={l} className={k ? 'th-sort' : ''} onClick={() => sortBy(k)}>{l}{f.sort === k && (f.direction === 'asc' ? <ArrowUp size={12} /> : <ArrowDown size={12} />)}</th>
              ))}</tr></thead>
              <tbody>{data.items.map(s => (
                <tr key={s.id} className="clickable-row" onClick={() => nav(`/admin/students/${s.id}`)}>
                  <td><div className="strong">{s.name}</div><div className="tiny faint">{s.email}</div></td>
                  <td>{s.student_code}</td>
                  <td className="small">{s.phone || '—'}</td>
                  <td className="small">{s.pass.pass_label || '—'}</td>
                  <td className="small nowrap">{s.pass.has_pass ? prettyDate(s.pass.purchase_date, { day: 'numeric', month: 'short', year: 'numeric' }) : '—'}</td>
                  <td className="small nowrap">{s.pass.has_pass ? prettyDate(s.pass.expiry_date, { day: 'numeric', month: 'short', year: 'numeric' }) : '—'}</td>
                  <td><RemainingBar p={s.pass} /></td>
                  <td><PassBadge p={s.pass} /></td>
                </tr>
              ))}</tbody>
            </table>
          </div></ViewAll>
          {pages > 1 && <div className="between"><span className="small muted">{fmt(data.total)} students · page {f.page} of {pages}</span>
            <div className="row"><button className="btn sm" disabled={f.page <= 1} onClick={() => setF({ ...f, page: f.page - 1 })}>Previous</button>
              <button className="btn sm" disabled={f.page >= pages} onClick={() => setF({ ...f, page: f.page + 1 })}>Next</button></div></div>}
        </>}
      </div>
      {adding && <AddStudent onClose={() => setAdding(false)} onDone={() => reload(true)} />}
    </div>
  )
}


