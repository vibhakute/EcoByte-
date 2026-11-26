import { useState } from 'react'
import { CalendarCheck, CalendarX, Percent, UtensilsCrossed } from 'lucide-react'
import { useApi } from '../api'
import { Card, Empty, ErrorState, Field, Loading, Modal, Seg, Stat, addDays, cap, fmt, pct, prettyDate, todayIso } from './ui'

const STATUS = {
  present: ['Present', 'cal-present'], absent: ['Absent', 'cal-absent'], closed: ['Holiday / closed', 'cal-closed'],
  booked: ['Upcoming booked meal', 'cal-booked'], today: ['Today (not recorded yet)', 'cal-today'], open: ['Not booked yet', 'cal-open'],
  outside: ['Outside pass', 'cal-outside'],
}

function rangeFor(preset, pass, custom) {
  const t = todayIso()
  switch (preset) {
    case 'p7': return { start: addDays(t, -7), end: t }
    case 'p30': return { start: addDays(t, -30), end: t }
    case 'all': return { start: pass?.first_start && pass.first_start < t ? pass.first_start : addDays(t, -30), end: t }
    case 'u7': return { start: t, end: addDays(t, 7) }
    case 'rest': return { start: t, end: pass?.expiry && pass.expiry > t ? pass.expiry : addDays(t, 7) }
    default: return custom
  }
}

function months(days) {
  const out = []
  for (const d of days) {
    const key = d.date.slice(0, 7)
    let m = out[out.length - 1]
    if (!m || m.key !== key) { m = { key, days: [] }; out.push(m) }
    m.days.push(d)
  }
  return out
}

/** path: '/student/attendance/calendar' or `/admin/students/${id}/attendance` */
export default function AttendanceCalendar({ path, initial = 'p30' }) {
  const [preset, setPreset] = useState(initial)
  const [custom, setCustom] = useState({ start: addDays(todayIso(), -14), end: todayIso() })
  const probe = useApi(path, { start: todayIso(), end: todayIso() })
  const r = rangeFor(preset, probe.data?.pass, custom)
  const { data, error, loading, reload } = useApi(path, r)
  const [day, setDay] = useState(null)
  const s = data?.summary
  return (
    <div className="stack">
      <div className="card card-pad row wrap" style={{ gap: 12, justifyContent: 'space-between' }}>
        <Seg value={preset} onChange={setPreset} options={[
          { value: 'p7', label: 'Previous 7 days' }, { value: 'p30', label: 'Previous 30 days' }, { value: 'all', label: 'Complete history' },
          { value: 'u7', label: 'Upcoming 7 days' }, { value: 'rest', label: 'Remaining pass period' }, { value: 'custom', label: 'Custom range' }]} />
        {preset === 'custom' && <div className="row wrap" style={{ gap: 8 }}>
          <Field label="From"><input type="date" className="input sm" value={custom.start} max={custom.end} onChange={e => setCustom({ ...custom, start: e.target.value })} /></Field>
          <Field label="To"><input type="date" className="input sm" value={custom.end} min={custom.start} onChange={e => setCustom({ ...custom, end: e.target.value })} /></Field>
        </div>}
      </div>
      <div className="grid g-4">
        <Stat tone="white" icon={UtensilsCrossed} label="Total mess days" value={fmt(s?.mess_days)} loading={!s} foot="Past days covered by the pass" />
        <Stat tone="green" icon={CalendarCheck} label="Present days" value={fmt(s?.present_days)} loading={!s} foot={s ? `${s.meals_attended} meals recorded` : ''} />
        <Stat tone="orange" icon={CalendarX} label="Absent days" value={fmt(s?.absent_days)} loading={!s} foot={s?.closed_days ? `${s.closed_days} holiday / closed days excluded` : 'No attendance recorded'} />
        <Stat tone="blue" icon={Percent} label="Attendance" value={s?.attendance_pct != null ? pct(s.attendance_pct, 0) : '—'} loading={!s} foot={s?.upcoming_booked ? `${s.upcoming_booked} upcoming booked days` : 'present ÷ mess days'} />
      </div>
      <Card title="Attendance calendar" subtitle={data ? `${prettyDate(data.range.start, { day: 'numeric', month: 'short', year: 'numeric' })} – ${prettyDate(data.range.end, { day: 'numeric', month: 'short', year: 'numeric' })}` : ''}
        actions={<div className="cal-legend">{['present', 'absent', 'closed', 'booked'].map(k => <span key={k}><i className={STATUS[k][1]} />{STATUS[k][0]}</span>)}</div>}>
        {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Loading rows={5} height={40} /> : !data.days.length ? <Empty /> : (
          <div className="stack" style={{ gap: 20 }}>
            {months(data.days).map(m => {
              const lead = (new Date(m.days[0].date + 'T00:00:00').getDay() + 6) % 7
              return (
                <div key={m.key}>
                  <div className="small strong" style={{ marginBottom: 8 }}>{prettyDate(m.key + '-01', { month: 'long', year: 'numeric' })}</div>
                  <div className="cal-grid">
                    {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(w => <div key={w} className="cal-head">{w}</div>)}
                    {Array.from({ length: lead }).map((_, i) => <div key={'b' + i} />)}
                    {m.days.map(d => (
                      <button key={d.date} className={`cal-cell ${STATUS[d.status][1]} ${d.date === todayIso() ? 'is-today' : ''}`}
                        title={`${prettyDate(d.date)} · ${STATUS[d.status][0]}`} onClick={() => setDay(d)}>
                        <b>{Number(d.date.slice(8))}</b>
                        <span className="cal-dots">{['breakfast', 'lunch', 'dinner'].map(k => {
                          const x = d.meals[k]
                          const c = x.present ? 'p' : x.closed ? 'c' : x.booking ? 'b' : x.plan === 'coming' ? 'b' : ''
                          return <i key={k} className={c} />
                        })}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )
            })}
            <p className="tiny faint">Past days show only attendance recorded at the counter. Future days show bookings and plans — they are never marked present or absent in advance.</p>
          </div>
        )}
      </Card>
      <Modal open={!!day} title={day ? prettyDate(day.date, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }) : ''} onClose={() => setDay(null)}>
        {day && <div className="stack" style={{ gap: 10 }}>
          <div><span className={`cal-pill ${STATUS[day.status][1]}`}>{STATUS[day.status][0]}</span>{day.closed_reason && <span className="small muted"> · {day.closed_reason}</span>}</div>
          {['breakfast', 'lunch', 'dinner'].map(k => {
            const x = day.meals[k]
            return (
              <div key={k} className="list-item">
                <span className="strong">{cap(k)}</span>
                <span className="small muted">{x.closed ? `Closed (${x.closed})` : x.present ? 'Present ✓' : x.booking ? `Booked ${x.booking.time} · ${x.booking.status === 'served' ? 'completed' : 'confirmed'}` : x.plan === 'coming' ? 'Planned: coming' : x.plan === 'not_coming' ? 'Planned: not attending' : day.date < todayIso() ? 'No attendance recorded' : 'Not booked'}</span>
              </div>
            )
          })}
        </div>}
      </Modal>
    </div>
  )
}
