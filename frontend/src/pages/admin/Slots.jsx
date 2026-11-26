import { useState } from 'react'
import { CalendarDays, CheckCircle2, Clock, Pencil, Plus, Ticket, Users, XCircle } from 'lucide-react'
import { api, useApi } from '../../api'
import { Badge, Card, Empty, ErrorState, Field, Loading, Meter, Modal, PageHeader, PageLoading, Stat, cap, fmt, todayIso, useAction } from '../../components/ui'
import { MEAL_ICON } from './Overview'

function BookingsModal({ slot, date, onClose, onChange }) {
  const { data, loading, reload } = useApi(slot ? `/admin/slots/${slot.id}/bookings` : null, { date })
  const [run] = useAction()
  return (
    <Modal open={!!slot} title={slot ? `${cap(slot.meal_type)} · ${slot.start}–${slot.end}` : ''} onClose={onClose} width={600}>
      {loading && !data ? <Loading /> : !data?.length ? <Empty icon={Users} title="No bookings for this slot" /> : (
        <table className="table compact">
          <thead><tr><th>Student</th><th>Code</th><th>Status</th><th></th></tr></thead>
          <tbody>{data.map(b => (
            <tr key={b.id}>
              <td><div className="small strong">{b.student}</div><div className="tiny faint">{b.student_code}</div></td>
              <td><code className="small">{b.code}</code></td>
              <td><Badge tone={b.status === 'booked' ? 'blue' : b.status === 'served' ? 'green' : ''}>{b.status === 'booked' ? 'Confirmed' : b.status === 'served' ? 'Completed' : 'Cancelled'}</Badge></td>
              <td className="right">{b.status === 'booked' && <button className="btn sm" onClick={async () => { if (await run(() => api(`/admin/bookings/${b.id}/served`, { method: 'POST' }), 'Marked as served (arrival recorded)')) { reload(true); onChange() } }}>Mark served</button>}</td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </Modal>
  )
}

export default function Slots() {
  const [date, setDate] = useState(todayIso())
  const { data, error, loading, reload } = useApi('/admin/slots', { date })
  const [run, busy] = useAction()
  const [view, setView] = useState(null)
  const [edit, setEdit] = useState(null)
  if (loading && !data) return <PageLoading />
  if (error) return <ErrorState error={error} onRetry={reload} />
  const act = data.slots.filter(s => s.active)
  const tot = k => act.reduce((a, s) => a + s[k], 0)

  async function save() {
    const body = { capacity: Number(edit.capacity), start_time: edit.start, end_time: edit.end, active: edit.active }
    const r = edit.id ? await run(() => api(`/admin/slots/${edit.id}`, { method: 'PATCH', body }), 'Slot updated')
      : await run(() => api('/admin/slots', { method: 'POST', body: { ...body, meal_type: edit.meal_type, start_time: edit.start, end_time: edit.end } }), 'Slot added')
    if (r) { setEdit(null); reload(true) }
  }

  return (
    <div className="stack">
      <PageHeader title="Slot Booking Management" subtitle="15-minute meal slots spread the rush. Bookings can never exceed capacity."
        actions={<>
          <label className="date-pill"><CalendarDays /><input type="date" value={date} onChange={e => e.target.value && setDate(e.target.value)} aria-label="Date" /></label>
          <button className="btn primary" onClick={() => setEdit({ meal_type: 'lunch', start: '14:00', end: '14:15', capacity: 40, active: true })}><Plus />Add slot</button>
        </>} />
      <div className="grid g-5">
        <Stat tone="white" icon={Clock} label="Available slots" value={fmt(act.length)} />
        <Stat tone="green" icon={Ticket} label="Total bookings" value={fmt(tot('booked'))} foot={`of ${fmt(tot('capacity'))} seats`} />
        <Stat tone="blue" icon={Users} label="Confirmed" value={fmt(tot('confirmed'))} />
        <Stat tone="orange" icon={CheckCircle2} label="Completed" value={fmt(tot('completed'))} />
        <Stat tone="purple" icon={XCircle} label="Cancelled" value={fmt(tot('cancelled'))} />
      </div>
      {['breakfast', 'lunch', 'dinner'].map(meal => {
        const list = data.slots.filter(s => s.meal_type === meal)
        const Icon = MEAL_ICON[meal]
        return (
          <Card key={meal} title={<><Icon />{cap(meal)}</>} subtitle={`${fmt(list.filter(s => s.active).reduce((a, s) => a + s.booked, 0))} booked · ${fmt(list.filter(s => s.active).reduce((a, s) => a + s.remaining, 0))} seats remaining`}>
            {!list.length ? <Empty title="No slots" /> : (
              <div className="table-wrap flush">
                <table className="table">
                  <thead><tr><th>Time</th><th style={{ width: '26%' }}>Bookings</th><th className="num">Confirmed</th><th className="num">Completed</th><th className="num">Cancelled</th><th className="num">Remaining</th><th>Status</th><th></th></tr></thead>
                  <tbody>{list.map(s => (
                    <tr key={s.id} style={{ opacity: s.active ? 1 : .55 }}>
                      <td className="strong nowrap">{s.start} – {s.end}</td>
                      <td><div className="row"><div style={{ flex: 1 }}><Meter value={s.booked} max={s.capacity} /></div><span className="small nowrap" style={{ width: 52 }}>{s.booked}/{s.capacity}</span></div></td>
                      <td className="num">{s.confirmed}</td><td className="num">{s.completed}</td><td className="num">{s.cancelled}</td>
                      <td className="num strong">{s.remaining}</td>
                      <td>{!s.active ? <Badge>Inactive</Badge> : s.remaining === 0 ? <Badge tone="red">Full</Badge> : <Badge tone="green">Open</Badge>}</td>
                      <td className="right nowrap">
                        <button className="btn sm ghost" onClick={() => setView(s)}>Bookings</button>
                        <button className="btn sm ghost" onClick={() => setEdit({ ...s })}><Pencil size={14} />Edit</button>
                      </td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            )}
          </Card>
        )
      })}
      <BookingsModal slot={view} date={date} onClose={() => setView(null)} onChange={() => reload(true)} />
      <Modal open={!!edit} title={edit?.id ? 'Edit slot' : 'Add slot'} onClose={() => setEdit(null)}
        footer={<><button className="btn ghost" onClick={() => setEdit(null)}>Cancel</button><button className="btn primary" onClick={save} disabled={busy}>Save</button></>}>
        {edit && (
          <div className="form-grid">
            <Field label="Meal"><select className="select" value={edit.meal_type} disabled={!!edit.id} onChange={e => setEdit({ ...edit, meal_type: e.target.value })}>{['breakfast', 'lunch', 'dinner'].map(m => <option key={m} value={m}>{cap(m)}</option>)}</select></Field>
            <Field label="Capacity" hint="Cannot go below future bookings"><input className="input" type="number" min="1" value={edit.capacity} onChange={e => setEdit({ ...edit, capacity: e.target.value })} /></Field>
            <Field label="Start"><input className="input" type="time" value={edit.start} onChange={e => setEdit({ ...edit, start: e.target.value })} /></Field>
            <Field label="End"><input className="input" type="time" value={edit.end} onChange={e => setEdit({ ...edit, end: e.target.value })} /></Field>
            <label className="check span-all"><input type="checkbox" checked={edit.active} onChange={e => setEdit({ ...edit, active: e.target.checked })} />Active (students can book it)</label>
          </div>
        )}
      </Modal>
    </div>
  )
}
