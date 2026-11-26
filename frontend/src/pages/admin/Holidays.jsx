import { useState } from 'react'
import { CalendarX, Megaphone, Pencil, Plus, Trash } from 'lucide-react'
import { api, useApi } from '../../api'
import { Alert, Badge, Card, Empty, ErrorState, Field, Loading, Modal, PageHeader, Tabs, cap, prettyDate, prettyTime, todayIso, useAction } from '../../components/ui'

const TYPES = [['national', 'National'], ['festival', 'Festival'], ['college', 'College'], ['special', 'Special']]
const TYPE_TONE = { national: 'blue', festival: 'orange', college: 'green', special: 'purple' }
const MEALS = ['breakfast', 'lunch', 'dinner']

function HolidayForm({ h, onClose, onSaved }) {
  const [f, setF] = useState(h || { name: '', date: todayIso(), holiday_type: 'festival', description: '', services: [...MEALS], message: '' })
  const [run, busy] = useAction()
  const full = f.services.length === 3
  const toggle = m => setF({ ...f, services: f.services.includes(m) ? f.services.filter(x => x !== m) : [...f.services, m] })
  async function save(publish) {
    if (publish && !window.confirm(`Publish "${f.name}"? All students will be notified, ${full ? 'the canteen will be closed all day' : `${f.services.join(', ')} will be unavailable`}, and existing bookings for those meals will be cancelled.`)) return
    const body = { name: f.name, date: f.date, holiday_type: f.holiday_type, description: f.description, services: f.services, message: f.message, publish }
    const r = await run(() => h?.id ? api(`/admin/holidays/${h.id}`, { method: 'PUT', body }) : api('/admin/holidays', { method: 'POST', body }),
      x => x.published ? `Published: ${x.published.students_notified} students notified, ${x.published.bookings_cancelled} bookings cancelled` : 'Holiday saved as draft')
    if (r) { onSaved(); onClose() }
  }
  return (
    <Modal open title={h?.id ? 'Edit holiday' : 'Create holiday'} onClose={onClose} width={620}
      footer={<>
        <button className="btn ghost" onClick={onClose}>Cancel</button>
        {!h?.published && <button className="btn" disabled={busy || !f.name || !f.services.length} onClick={() => save(false)}>Save as draft</button>}
        <button className="btn primary" disabled={busy || !f.name || !f.services.length} onClick={() => save(true)}><Megaphone />{h?.published ? 'Save & notify again' : 'Publish announcement'}</button>
      </>}>
      <div className="form-grid">
        <Field label="Holiday name" className="span-all"><input className="input" value={f.name} onChange={e => setF({ ...f, name: e.target.value })} placeholder="e.g. Diwali" autoFocus /></Field>
        <Field label="Holiday date" hint="Future dates are scheduled; meals close on that day"><input className="input" type="date" min={todayIso()} value={f.date} onChange={e => setF({ ...f, date: e.target.value })} /></Field>
        <Field label="Holiday type"><select className="select" value={f.holiday_type} onChange={e => setF({ ...f, holiday_type: e.target.value })}>{TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
        <div className="field span-all"><label>Affected services</label>
          <div className="row wrap">
            <label className="check"><input type="checkbox" checked={full} onChange={e => setF({ ...f, services: e.target.checked ? [...MEALS] : [] })} /><b>Full day</b></label>
            {MEALS.map(m => <label key={m} className="check"><input type="checkbox" checked={f.services.includes(m)} onChange={() => toggle(m)} />{cap(m)}</label>)}
          </div>
        </div>
        <Field label="Description" className="span-all"><textarea className="textarea" value={f.description} onChange={e => setF({ ...f, description: e.target.value })} placeholder="Internal note (optional)" /></Field>
        <Field label="Notification message" className="span-all" hint="Shown to students on their dashboard"><textarea className="textarea" value={f.message} onChange={e => setF({ ...f, message: e.target.value })} placeholder="e.g. Happy Diwali! The canteen will be closed. Lunch resumes on Monday." /></Field>
      </div>
    </Modal>
  )
}

export default function Holidays() {
  const [scope, setScope] = useState('upcoming')
  const { data, error, loading, reload } = useApi('/admin/holidays', { scope })
  const settings = useApi('/admin/settings')
  const [form, setForm] = useState(null)
  const [run, busy] = useAction()
  const publish = async h => {
    if (!window.confirm(`Publish "${h.name}" (${prettyDate(h.date)})? Students will be notified and affected bookings cancelled.`)) return
    if (await run(() => api(`/admin/holidays/${h.id}/publish`, { method: 'POST' }), r => `${r.published.students_notified} students notified`)) reload(true)
  }
  const remove = async h => {
    if (!window.confirm(`Delete "${h.name}"?${h.published ? ' Students will be told the canteen is open as usual.' : ''}`)) return
    if (await run(() => api(`/admin/holidays/${h.id}`, { method: 'DELETE' }), 'Holiday deleted')) reload(true)
  }
  return (
    <div className="stack">
      <PageHeader title="Holiday Management" subtitle="Announce national, festival and college holidays. Published holidays close the selected meals and notify every student."
        actions={<button className="btn primary" onClick={() => setForm({})}><Plus />Create holiday</button>} />
      {settings.data && <Alert tone="info">Pass policy: {settings.data.holiday_extends_pass
        ? 'full-day holidays automatically extend active passes by 1 day.' : 'holidays do not change mess pass validity. You can extend passes manually in Student Management, or change this in Settings.'}</Alert>}
      <Tabs value={scope} onChange={setScope} options={[{ value: 'upcoming', label: 'Upcoming' }, { value: 'past', label: 'Past' }, { value: 'all', label: 'All' }]} />
      <Card viewAll>
        {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Loading rows={5} /> : !data.length ? (
          <Empty icon={CalendarX} title={scope === 'upcoming' ? 'No upcoming holidays' : 'No holidays'}>Create one to inform students in advance.</Empty>
        ) : (
          <div className="table-wrap flush" style={{ marginTop: -14 }}>
            <table className="table">
              <thead><tr><th>Date</th><th>Holiday</th><th>Type</th><th>Affected services</th><th>Status</th><th></th></tr></thead>
              <tbody>{data.map(h => (
                <tr key={h.id}>
                  <td className="nowrap strong">{prettyDate(h.date, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })}</td>
                  <td><div className="strong">{h.name}</div>{h.message && <div className="tiny faint" style={{ maxWidth: 360 }}>{h.message}</div>}</td>
                  <td><Badge tone={TYPE_TONE[h.holiday_type]}>{cap(h.holiday_type)}</Badge></td>
                  <td className="small">{h.services.length ? h.services_label : <span className="faint">Canteen open (observance only)</span>}</td>
                  <td>{h.published ? <Badge tone="green">Published{h.published_at ? ` · ${prettyTime(h.published_at)}` : ''}</Badge> : <Badge tone="amber">Draft</Badge>}</td>
                  <td className="right nowrap">{!h.past && <>
                    {!h.published && <button className="btn sm primary" disabled={busy} onClick={() => publish(h)}><Megaphone />Publish</button>}
                    <button className="btn sm ghost" onClick={() => setForm(h)}><Pencil size={14} />Edit</button>
                    <button className="btn sm ghost icon-btn danger" aria-label={`Delete ${h.name}`} disabled={busy} onClick={() => remove(h)}><Trash /></button>
                  </>}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </Card>
      {form && <HolidayForm h={form.id ? form : null} onClose={() => setForm(null)} onSaved={() => reload(true)} />}
    </div>
  )
}
