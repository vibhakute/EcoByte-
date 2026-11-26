import { useEffect, useState } from 'react'
import { api, useApi } from '../../api'
import { useAuth } from '../../auth'
import { Card, ErrorState, Field, PageHeader, PageLoading, fmt, prettyDate, useAction } from '../../components/ui'

export default function StudentProfile() {
  const { data, error, loading, reload } = useApi('/student/profile')
  const { update } = useAuth()
  const [f, setF] = useState(null)
  const [pw, setPw] = useState({ current_password: '', new_password: '', confirm: '' })
  const [run, busy] = useAction()
  useEffect(() => { if (data) setF({ name: data.name, phone: data.phone || '', department: data.department || '', year_of_study: data.year_of_study || '' }) }, [data])

  if (loading && !data) return <PageLoading />
  if (error) return <ErrorState error={error} onRetry={reload} />
  if (!f) return null

  async function save(e) {
    e.preventDefault()
    const r = await run(() => api('/student/profile', { method: 'PATCH', body: { ...f, year_of_study: f.year_of_study ? Number(f.year_of_study) : null } }), 'Profile updated')
    if (r) update(r)
  }
  async function changePw(e) {
    e.preventDefault()
    if (pw.new_password !== pw.confirm) return run(async () => { throw new Error('New passwords do not match') })
    const r = await run(() => api('/student/password', { method: 'POST', body: { current_password: pw.current_password, new_password: pw.new_password } }), 'Password changed')
    if (r) setPw({ current_password: '', new_password: '', confirm: '' })
  }
  const set = k => e => setF({ ...f, [k]: e.target.value })

  return (
    <div className="stack">
      <PageHeader title="Profile" subtitle="Your account details." />
      <div className="grid g-main">
        <Card title="Personal information">
          <form className="stack" onSubmit={save}>
            <div className="form-grid">
              <Field label="Full name" className="span-2"><input className="input" value={f.name} onChange={set('name')} required minLength={2} /></Field>
              <Field label="Email" hint="Contact the canteen office to change your email"><input className="input" value={data.email} disabled /></Field>
              <Field label="Student ID"><input className="input" value={data.student_code || ''} disabled /></Field>
              <Field label="Phone"><input className="input" value={f.phone} onChange={set('phone')} /></Field>
              <Field label="Year">
                <select className="select" value={f.year_of_study} onChange={set('year_of_study')}>
                  <option value="">—</option>{[1, 2, 3, 4, 5].map(y => <option key={y} value={y}>Year {y}</option>)}
                </select>
              </Field>
              <Field label="Department" className="span-2"><input className="input" value={f.department} onChange={set('department')} /></Field>
            </div>
            <div><button className="btn primary" disabled={busy}>Save changes</button></div>
          </form>
        </Card>
        <div className="stack">
          <Card title="Summary">
            <dl className="kv">
              <dt>Member since</dt><dd>{prettyDate(data.member_since, { month: 'short', year: 'numeric' })}</dd>
              <dt>Responses submitted</dt><dd>{fmt(data.total_responses)}</dd>
              <dt>Reward points</dt><dd>{fmt(data.balance)}</dd>
            </dl>
          </Card>
          <Card title="Change password">
            <form className="stack" onSubmit={changePw}>
              <Field label="Current password"><input className="input" type="password" autoComplete="current-password" value={pw.current_password} onChange={e => setPw({ ...pw, current_password: e.target.value })} required /></Field>
              <Field label="New password" hint="At least 8 characters"><input className="input" type="password" autoComplete="new-password" minLength={8} value={pw.new_password} onChange={e => setPw({ ...pw, new_password: e.target.value })} required /></Field>
              <Field label="Confirm new password"><input className="input" type="password" autoComplete="new-password" value={pw.confirm} onChange={e => setPw({ ...pw, confirm: e.target.value })} required /></Field>
              <div><button className="btn" disabled={busy}>Update password</button></div>
            </form>
          </Card>
        </div>
      </div>
    </div>
  )
}
