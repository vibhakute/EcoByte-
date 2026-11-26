import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, CalendarPlus, KeyRound, Pause, Pencil, Play, RefreshCw, Ticket } from 'lucide-react'
import { api, useApi } from '../../api'
import AttendanceCalendar from '../../components/AttendanceCalendar'
import {
  Alert, Badge, Card, Empty, ErrorState, Field, Modal, PageLoading, Tabs, addDays, fmt, initials, inr, prettyDate, prettyTime, useAction,
} from '../../components/ui'
import { PassBadge } from './Students'

const REASONS = [['student_leave', 'Student leave'], ['medical_leave', 'Medical leave'], ['college_holiday', 'College holiday'],
  ['special_permission', 'Special permission'], ['other', 'Other']]
const D = s => prettyDate(s, { day: 'numeric', month: 'short', year: 'numeric' })
const uuid = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`)

function ExtendModal({ student, days, onClose, onDone }) {
  const [f, setF] = useState({ days, reason: 'student_leave', note: '', leave_from: '', leave_to: '', request_key: uuid() })
  const [run, busy] = useAction()
  const p = student.pass
  const newExpiry = addDays(p.expiry_date, Number(f.days) || 0)
  async function save() {
    const r = await run(() => api(`/admin/students/${student.id}/extend`, { method: 'POST', body: {
      ...f, days: Number(f.days), leave_from: f.leave_from || null, leave_to: f.leave_to || null } }),
    x => x.duplicate ? 'This extension was already applied' : `Pass extended to ${D(x.new_expiry)}`)
    if (r) { onDone(); onClose() }
  }
  return (
    <Modal open title={`Extend mess pass · ${student.name}`} onClose={onClose}
      footer={<><button className="btn ghost" onClick={onClose}>Cancel</button><button className="btn primary" disabled={busy || !(Number(f.days) >= 1)} onClick={save}>Confirm extension</button></>}>
      <div className="stack">
        <div className="form-grid">
          <Field label="Days to add"><input className="input" type="number" min="1" max="90" value={f.days} onChange={e => setF({ ...f, days: e.target.value })} /></Field>
          <Field label="Reason"><select className="select" value={f.reason} onChange={e => setF({ ...f, reason: e.target.value })}>{REASONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
          <Field label="Leave from (optional)"><input className="input" type="date" value={f.leave_from} onChange={e => setF({ ...f, leave_from: e.target.value })} /></Field>
          <Field label="Leave to (optional)"><input className="input" type="date" value={f.leave_to} onChange={e => setF({ ...f, leave_to: e.target.value })} /></Field>
          <Field label="Note" className="span-all"><input className="input" value={f.note} onChange={e => setF({ ...f, note: e.target.value })} placeholder="e.g. Going home for a family function" /></Field>
        </div>
        <div className="formula">Expiry: {D(p.expiry_date)} → <b>{D(newExpiry)}</b> (+{f.days || 0} days)</div>
        <p className="tiny faint">This changes only the pass validity. It is not an attendance record and does not mark the student absent or present.</p>
      </div>
    </Modal>
  )
}

function RenewModal({ student, onClose, onDone }) {
  const p = student.pass
  const defaultStart = p.has_pass && p.status !== 'expired' ? addDays(p.expiry_date, 1) : new Date().toISOString().slice(0, 10)
  const [f, setF] = useState({ pass_type: p.pass_type || 'monthly', start_date: defaultStart })
  const [run, busy] = useAction()
  const days = f.pass_type === 'monthly' ? 30 : 180
  async function save() {
    if (await run(() => api(`/admin/students/${student.id}/renew`, { method: 'POST', body: f }), 'Pass renewed')) { onDone(); onClose() }
  }
  return (
    <Modal open title={`Renew mess pass · ${student.name}`} onClose={onClose}
      footer={<><button className="btn ghost" onClick={onClose}>Cancel</button><button className="btn primary" disabled={busy} onClick={save}>Confirm renewal</button></>}>
      <div className="form-grid">
        <Field label="Pass type"><select className="select" value={f.pass_type} onChange={e => setF({ ...f, pass_type: e.target.value })}><option value="monthly">Monthly (30 days)</option><option value="six_month">Six-month (180 days)</option></select></Field>
        <Field label="Start date" hint="Must not overlap the current pass"><input className="input" type="date" value={f.start_date} onChange={e => setF({ ...f, start_date: e.target.value })} /></Field>
        <div className="formula span-all">Valid {D(f.start_date)} – <b>{D(addDays(f.start_date, days - 1))}</b> ({days} days)</div>
      </div>
    </Modal>
  )
}

function EditModal({ s, onClose, onDone }) {
  const [f, setF] = useState({ name: s.name, email: s.email, phone: s.phone || '', department: s.department || '', year_of_study: s.year_of_study || '' })
  const [run, busy] = useAction()
  async function save() {
    if (await run(() => api(`/admin/students/${s.id}`, { method: 'PATCH', body: { ...f, phone: f.phone || null, year_of_study: f.year_of_study ? Number(f.year_of_study) : null } }), 'Details updated')) { onDone(); onClose() }
  }
  const set = k => e => setF({ ...f, [k]: e.target.value })
  return (
    <Modal open title="Edit personal information" onClose={onClose}
      footer={<><button className="btn ghost" onClick={onClose}>Cancel</button><button className="btn primary" disabled={busy} onClick={save}>Save</button></>}>
      <div className="form-grid">
        <Field label="Full name" className="span-all"><input className="input" value={f.name} onChange={set('name')} /></Field>
        <Field label="Email"><input className="input" value={f.email} onChange={set('email')} /></Field>
        <Field label="Contact number"><input className="input" value={f.phone} onChange={set('phone')} /></Field>
        <Field label="Department"><input className="input" value={f.department} onChange={set('department')} /></Field>
        <Field label="Year"><select className="select" value={f.year_of_study} onChange={set('year_of_study')}><option value="">—</option>{[1, 2, 3, 4, 5].map(y => <option key={y} value={y}>Year {y}</option>)}</select></Field>
      </div>
    </Modal>
  )
}

export default function StudentProfile() {
  const { id } = useParams()
  const { data: s, error, loading, reload } = useApi(`/admin/students/${id}`)
  const [tab, setTab] = useState('pass')
  const [ext, setExt] = useState(null)
  const [renew, setRenew] = useState(false)
  const [edit, setEdit] = useState(false)
  const [temp, setTemp] = useState(null)
  const [run, busy] = useAction()
  if (loading && !s) return <PageLoading />
  if (error) return <ErrorState error={error} onRetry={reload} />
  const p = s.pass

  async function suspend() {
    const to = !s.suspended
    const reason = to ? window.prompt(`Suspend ${s.name}'s mess pass? Upcoming bookings will be cancelled.\nReason (shown to the student):`, '') : ''
    if (to && reason === null) return
    if (!to && !window.confirm(`Reactivate ${s.name}?`)) return
    if (await run(() => api(`/admin/students/${s.id}/suspend`, { method: 'POST', body: { suspended: to, reason: reason || '' } }), to ? 'Student suspended' : 'Student reactivated')) reload(true)
  }
  async function resetPw() {
    if (!window.confirm(`Reset ${s.name}'s password? Their current password stops working.`)) return
    const r = await run(() => api(`/admin/students/${s.id}/reset-password`, { method: 'POST' }), 'Temporary password created')
    if (r) setTemp(r.temporary_password)
  }

  return (
    <div className="stack">
      <Link to="/admin/students" className="btn ghost sm" style={{ alignSelf: 'flex-start' }}><ArrowLeft />All students</Link>
      <div className="card card-pad between wrap" style={{ gap: 16 }}>
        <div className="row" style={{ gap: 16 }}>
          <span className="avatar lg">{initials(s.name)}</span>
          <div><h1 style={{ fontSize: 22 }}>{s.name}</h1><div className="muted small">{s.student_code} · {s.email}{s.phone ? ` · ${s.phone}` : ''}</div>
            <div className="row mt-8"><PassBadge p={p} /><Badge tone="blue"><Ticket />{fmt(s.token_balance)} tokens</Badge></div></div>
        </div>
        <div className="row wrap">
          <button className="btn" onClick={() => setEdit(true)}><Pencil />Edit</button>
          <button className="btn" disabled={busy} onClick={resetPw}><KeyRound />Reset password</button>
          <button className={`btn ${s.suspended ? 'primary' : 'danger'}`} disabled={busy} onClick={suspend}>{s.suspended ? <><Play />Reactivate</> : <><Pause />Suspend</>}</button>
        </div>
      </div>
      {temp && <Alert tone="success">Temporary password: <b style={{ fontFamily: 'monospace' }}>{temp}</b>. Share it privately; it is shown only once.</Alert>}
      {s.suspended && <Alert tone="warn">This student is suspended: they can sign in but cannot confirm or book meals.</Alert>}

      <Tabs value={tab} onChange={setTab} options={[{ value: 'pass', label: 'Mess subscription' }, { value: 'attendance', label: 'Attendance history' }, { value: 'info', label: 'Personal information' }]} />
      {tab === 'pass' && <>
        <div className="grid g-main">
          <Card title="Mess subscription">
            {!p.has_pass ? <Empty icon={Ticket} title="No mess pass">Create one with “Renew pass”.</Empty> : (
              <div className="stack">
                <div className="between wrap" style={{ alignItems: 'flex-end' }}>
                  <div><div className="small muted">Remaining validity</div><div style={{ fontSize: 40, fontWeight: 800, letterSpacing: '-0.03em', lineHeight: 1.1 }}>{p.remaining_days} <span className="muted" style={{ fontSize: 16, fontWeight: 500 }}>of {p.total_days} days</span></div></div>
                  <PassBadge p={p} />
                </div>
                <div className={`pass-bar ${p.color}`}><i style={{ width: `${p.progress_pct}%` }} /></div>
                <div className="between small muted"><span>Used: <b>{p.used_days} days</b></span><span>Remaining: <b>{p.remaining_days} days</b></span></div>
                <dl className="kv">
                  <dt>Pass type</dt><dd>{p.pass_label}</dd>
                  <dt>Purchase date</dt><dd>{D(p.purchase_date)}</dd>
                  <dt>Start date</dt><dd>{D(p.start_date)}</dd>
                  <dt>Expiry date</dt><dd>{D(p.expiry_date)}</dd>
                  <dt>Total duration</dt><dd>{p.total_days} days{p.extension_days ? ` (${p.base_days} + ${p.extension_days} extended)` : ''}</dd>
                  <dt>Subscription status</dt><dd>{p.label}</dd>
                </dl>
              </div>
            )}
          </Card>
          <Card title="Admin actions" subtitle="Extensions follow the mess policy and are recorded with a reason">
            <div className="stack" style={{ gap: 10 }}>
              <div className="small strong">Extend pass (leave, holidays, special permission)</div>
              <div className="row wrap">
                {[2, 5, 7].map(n => <button key={n} className="btn soft" disabled={!p.has_pass} onClick={() => setExt(n)}><CalendarPlus />+{n} days</button>)}
                <button className="btn" disabled={!p.has_pass} onClick={() => setExt('')}>Custom…</button>
              </div>
              <div className="small strong mt-8">Renewal</div>
              <button className="btn primary" onClick={() => setRenew(true)}><RefreshCw />Renew pass</button>
              <div className="small strong mt-8">Attendance</div>
              <button className="btn" onClick={() => setTab('attendance')}>View attendance history</button>
              {s.attendance_summary && <p className="tiny faint">{s.attendance_summary.present_days} present / {s.attendance_summary.mess_days} mess days recorded{s.attendance_summary.attendance_pct != null ? ` (${s.attendance_summary.attendance_pct}%)` : ''}.</p>}
            </div>
          </Card>
        </div>
        <Card viewAll title="Extension history">
          {!s.extensions.length ? <Empty title="No extensions yet" /> : (
            <div className="table-wrap flush"><table className="table">
              <thead><tr><th>Date</th><th>Previous expiry</th><th className="num">Added</th><th>New expiry</th><th>Reason</th><th>Note</th><th>By</th></tr></thead>
              <tbody>{s.extensions.map(e => (
                <tr key={e.id}><td className="small nowrap">{prettyTime(e.created_at)}</td><td>{D(e.previous_expiry)}</td><td className="num strong">+{e.added_days}</td><td className="strong">{D(e.new_expiry)}</td>
                  <td><Badge tone="blue">{e.reason_label}</Badge></td><td className="small muted">{e.note || '—'}{e.leave_from && <div className="tiny">Leave {D(e.leave_from)} – {e.leave_to ? D(e.leave_to) : '…'}</div>}</td><td className="small">{e.admin}</td></tr>
              ))}</tbody></table></div>
          )}
        </Card>
        <Card viewAll title="Subscription history">
          {!s.subscriptions.length ? <Empty title="No passes yet" /> : (
            <div className="table-wrap flush"><table className="table">
              <thead><tr><th>Pass</th><th>Purchased</th><th>Valid</th><th className="num">Base days</th><th className="num">Price</th><th>State</th></tr></thead>
              <tbody>{s.subscriptions.map(x => (
                <tr key={x.id}><td className="strong">{x.pass_label}</td><td>{D(x.purchase_date)}</td><td className="nowrap">{D(x.start_date)} – {D(x.expiry_date)}</td><td className="num">{x.base_days}</td><td className="num">{inr(x.price)}</td>
                  <td><Badge tone={x.state === 'current' ? 'green' : x.state === 'upcoming' ? 'blue' : ''}>{x.state}</Badge></td></tr>
              ))}</tbody></table></div>
          )}
        </Card>
      </>}
      {tab === 'attendance' && <AttendanceCalendar path={`/admin/students/${s.id}/attendance`} initial="all" />}
      {tab === 'info' && (
        <Card title="Personal information" actions={<button className="btn sm" onClick={() => setEdit(true)}><Pencil />Edit</button>}>
          <dl className="kv" style={{ maxWidth: 520 }}>
            <dt>Full name</dt><dd>{s.name}</dd><dt>Student ID</dt><dd>{s.student_code}</dd><dt>Email</dt><dd>{s.email}</dd>
            <dt>Contact</dt><dd>{s.phone || '—'}</dd><dt>Department</dt><dd>{s.department || '—'}</dd><dt>Year</dt><dd>{s.year_of_study ? `Year ${s.year_of_study}` : '—'}</dd>
            <dt>Registered</dt><dd>{s.created_at ? prettyTime(s.created_at) : '—'}</dd>
          </dl>
        </Card>
      )}
      {ext !== null && <ExtendModal student={s} days={ext} onClose={() => setExt(null)} onDone={() => reload(true)} />}
      {renew && <RenewModal student={s} onClose={() => setRenew(false)} onDone={() => reload(true)} />}
      {edit && <EditModal s={s} onClose={() => setEdit(false)} onDone={() => reload(true)} />}
    </div>
  )
}
