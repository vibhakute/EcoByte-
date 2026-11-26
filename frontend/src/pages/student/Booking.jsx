import { useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, Clock, Lock, RefreshCw, Ticket, X } from 'lucide-react'
import { api, useApi } from '../../api'
import {
  Alert, Badge, Card, Empty, ErrorState, Loading, Meter, Modal, PageHeader, Seg, Tabs, addDays, cap, prettyDate, prettyTime, todayIso, useAction,
} from '../../components/ui'

export const STATE = { confirmed: ['Confirmed', 'green'], locked: ['Locked', 'blue'], completed: ['Completed', 'solid'], cancelled: ['Cancelled', ''] }
const StateBadge = ({ s }) => <Badge tone={STATE[s][1]} icon={s === 'locked' ? Lock : s === 'confirmed' ? CheckCircle2 : undefined}>{STATE[s][0]}</Badge>

export default function StudentBooking() {
  const t = todayIso()
  const days = Array.from({ length: 8 }, (_, i) => addDays(t, i)).filter(d => new Date(d + 'T00:00:00').getDay() !== 0)
  const [date, setDate] = useState(t)
  const [meal, setMeal] = useState(new Date().getHours() < 9 ? 'breakfast' : new Date().getHours() < 14 ? 'lunch' : 'dinner')
  const [pick, setPick] = useState(null)
  const [confirmed, setConfirmed] = useState(null)
  const [hist, setHist] = useState('upcoming')
  const slots = useApi('/student/slots', { date })
  const bookings = useApi('/student/bookings')
  const [run, busy] = useAction()

  const list = slots.data?.slots[meal] || []
  const mine = list.find(s => s.mine)
  const closedReason = slots.data?.closed_meals?.[meal]
  const declined = slots.data?.attendance?.[meal] === 'not_coming'
  const noPass = slots.data && !slots.data.has_pass
  const blocked = closedReason || declined || noPass

  async function book() {
    const r = pick.change
      ? await run(() => api(`/student/bookings/${mine.mine.id}/change`, { method: 'POST', body: { slot_id: pick.id } }))
      : await run(() => api('/student/bookings', { method: 'POST', body: { slot_id: pick.id, date } }))
    if (r) { setConfirmed(r); setPick(null); slots.reload(true); bookings.reload(true) }
  }
  async function cancel(b) {
    if (!window.confirm(`Cancel your ${b.meal_type} booking on ${prettyDate(b.date)} at ${b.start}?`)) return
    if (await run(() => api(`/student/bookings/${b.id}/cancel`, { method: 'POST' }), 'Booking cancelled')) { slots.reload(true); bookings.reload(true); setConfirmed(null) }
  }

  const all = bookings.data || []
  const groups = {
    today: all.filter(b => b.date === t && b.state !== 'cancelled'),
    upcoming: all.filter(b => b.date > t && b.state !== 'cancelled').sort((a, b) => a.date.localeCompare(b.date)),
    previous: all.filter(b => b.date < t && b.state !== 'cancelled'),
    cancelled: all.filter(b => b.state === 'cancelled'),
  }

  return (
    <div className="stack">
      <PageHeader title="Book a meal slot" subtitle={`Pick a 15-minute window to skip the queue. Book, change or cancel up to ${slots.data?.cancel_minutes ?? 60} minutes before your slot starts.`} />

      {confirmed && (
        <div className="card card-pad" style={{ borderColor: 'var(--brand-600)', background: 'var(--brand-50)' }}>
          <div className="between wrap">
            <div className="row" style={{ gap: 12 }}><CheckCircle2 size={30} color="var(--brand)" />
              <div><div className="strong">Booking confirmed</div><div className="small muted">{cap(confirmed.meal_type)} · {prettyDate(confirmed.date, { weekday: 'long', day: 'numeric', month: 'short' })} · {confirmed.start} – {confirmed.end}</div>
                <div className="tiny faint">Change or cancel until {prettyTime(confirmed.deadline)}</div></div></div>
            <div className="right"><div className="tiny faint">Show this code at the counter</div><div className="strong" style={{ fontSize: 22, letterSpacing: '.05em' }}>{confirmed.code}</div></div>
          </div>
        </div>
      )}

      <Card>
        <div className="stack" style={{ gap: 14 }}>
          <div className="row" style={{ overflowX: 'auto', paddingBottom: 2 }}>
            {days.map((d, i) => <button key={d} className={`btn sm ${d === date ? 'primary' : ''}`} onClick={() => { setDate(d); setConfirmed(null) }}>{i === 0 ? 'Today' : i === 1 ? 'Tomorrow' : prettyDate(d, { weekday: 'short', day: 'numeric' })}</button>)}
          </div>
          <Seg value={meal} onChange={setMeal} options={['breakfast', 'lunch', 'dinner']} />
          {slots.error ? <ErrorState error={slots.error} onRetry={slots.reload} /> : slots.loading && !slots.data ? <Loading rows={3} height={60} /> : (
            <>
              {slots.data.menu?.[meal]?.length > 0 && <div className="small muted">On the menu: <b>{slots.data.menu[meal].join(', ')}</b></div>}
              {noPass && <Alert tone="error" title="No active mess pass for this date.">{slots.data.pass?.status === 'suspended' ? 'Your pass is suspended. Please contact the canteen office.' : <>Only students with an active pass can book meals. <Link to="/student" className="strong">Renew your pass</Link>.</>}</Alert>}
              {closedReason && <Alert tone="warn" title={`${cap(meal)} unavailable:`}>{closedReason}. Bookings are not possible for this meal.</Alert>}
              {declined && !closedReason && <Alert tone="warn">You marked yourself <b>not attending</b> {meal} on this day. <Link to="/student/attendance" className="strong">Change your plan</Link> to book.</Alert>}
              {mine && <Alert tone="success">Booked for <b>{mine.start} – {mine.end}</b> · code <b>{mine.mine.code}</b> · {mine.mine.state === 'locked' ? 'locked (deadline passed)' : `change or cancel until ${prettyTime(mine.mine.deadline)}`}. Pick another slot below to change it.</Alert>}
              {!list.length ? <Empty icon={Clock} title={`No ${meal} slots configured`} /> : (
                <div className="slot-grid">
                  {list.map(s => {
                    const status = s.mine ? s.mine.state : s.past ? 'closed' : s.available === 0 ? 'full' : 'open'
                    const disabled = !!blocked || (!s.mine && (s.past || s.available === 0)) || (mine && mine.mine.state !== 'confirmed')
                    return (
                      <button key={s.id} className={`slot ${s.mine ? 'mine' : ''} ${pick?.id === s.id ? 'selected' : ''}`} disabled={disabled && !s.mine}
                        onClick={() => !s.mine && setPick({ ...s, change: !!mine })}>
                        <span className="time">{s.start}</span>
                        <Meter value={s.booked} max={s.capacity} />
                        <span className="tiny faint">{s.mine ? `Your slot · ${STATE[s.mine.state][0]}` : status === 'closed' ? 'Booking closed' : status === 'full' ? 'Full' : `${s.available} of ${s.capacity} left`}</span>
                      </button>
                    )
                  })}
                </div>
              )}
            </>
          )}
        </div>
      </Card>

      <Card viewAll title={<><Ticket />My bookings</>} actions={<Tabs value={hist} onChange={setHist} options={[
        { value: 'today', label: `Today (${groups.today.length})` }, { value: 'upcoming', label: `Upcoming (${groups.upcoming.length})` },
        { value: 'previous', label: 'Previous' }, { value: 'cancelled', label: 'Cancelled' }]} />}>
        {bookings.loading && !bookings.data ? <Loading /> : !groups[hist].length ? <Empty icon={Ticket} title={`No ${hist} bookings`} /> : (
          <div className="list">{groups[hist].map(b => (
            <div className="list-item" key={b.id}>
              <div><div className="small strong">{cap(b.meal_type)} · {b.start} – {b.end}</div>
                <div className="tiny faint">{prettyDate(b.date, { weekday: 'long', day: 'numeric', month: 'short' })} · {b.code}{b.state === 'confirmed' ? ` · changeable until ${prettyTime(b.deadline)}` : ''}</div></div>
              <div className="row"><StateBadge s={b.state} />
                {b.state === 'confirmed' && <>
                  <button className="btn sm ghost" onClick={() => { setDate(b.date); setMeal(b.meal_type); window.scrollTo({ top: 0, behavior: 'smooth' }) }}><RefreshCw />Change</button>
                  <button className="btn sm danger" disabled={busy} onClick={() => cancel(b)}><X />Cancel</button></>}
              </div>
            </div>
          ))}</div>
        )}
      </Card>

      <Modal open={!!pick} title={pick?.change ? 'Change booking' : 'Confirm booking'} onClose={() => setPick(null)}
        footer={<><button className="btn ghost" onClick={() => setPick(null)}>Back</button><button className="btn primary" onClick={book} disabled={busy}>{busy ? 'Saving…' : pick?.change ? 'Move my booking' : 'Confirm booking'}</button></>}>
        {pick && (
          <dl className="kv">
            <dt>Meal</dt><dd>{cap(meal)}</dd>
            <dt>Date</dt><dd>{prettyDate(date, { weekday: 'long', day: 'numeric', month: 'long' })}</dd>
            {pick.change && <><dt>Current slot</dt><dd>{mine.start} – {mine.end}</dd></>}
            <dt>{pick.change ? 'New slot' : 'Time'}</dt><dd>{pick.start} – {pick.end}</dd>
            <dt>Seats left</dt><dd>{pick.available} of {pick.capacity}</dd>
            <dt>Change / cancel until</dt><dd>{prettyTime(pick.deadline)}</dd>
          </dl>
        )}
        <p className="tiny faint mt-12">A booking reserves your seat; attendance is recorded when you are served at the counter.</p>
      </Modal>
    </div>
  )
}
