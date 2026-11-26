import { useState } from 'react'
import { CalendarCheck, CheckCircle2, Clock, Gift, UtensilsCrossed, X } from 'lucide-react'
import { useApi } from '../../api'
import { Badge, Card, Empty, ErrorState, Field, PageHeader, PageLoading, Stat, Tabs, addDays, cap, fmt, prettyDate, prettyTime, todayIso } from '../../components/ui'

export default function StudentHistory() {
  const [r, setR] = useState({ start: addDays(todayIso(), -30), end: addDays(todayIso(), 14) })
  const [tab, setTab] = useState('attendance')
  const { data, error, loading, reload } = useApi('/student/history', r)
  if (loading && !data) return <PageLoading />
  if (error) return <ErrorState error={error} onRetry={reload} />
  const p = data.participation
  return (
    <div className="stack">
      <PageHeader title="History" subtitle="Your attendance, meal bookings and reward points."
        actions={<div className="row wrap" style={{ gap: 10, alignItems: 'flex-end' }}>
          <Field label="From"><input type="date" className="input sm" value={r.start} onChange={e => setR({ ...r, start: e.target.value })} /></Field>
          <Field label="To"><input type="date" className="input sm" value={r.end} onChange={e => setR({ ...r, end: e.target.value })} /></Field>
        </div>} />
      <div className="grid g-4">
        <Stat tone="green" icon={CalendarCheck} label="Meals confirmed" value={fmt(p.meals_confirmed)} foot={`${p.meals_declined} declined`} />
        <Stat tone="blue" icon={UtensilsCrossed} label="Meals attended" value={fmt(p.meals_attended)} foot="recorded at the counter" />
        <Stat tone="orange" icon={Clock} label="Slot bookings" value={fmt(p.bookings)} />
        <Stat tone="purple" icon={Gift} label="Points earned" value={fmt(p.points_earned)} />
      </div>
      <Tabs value={tab} onChange={setTab} options={[{ value: 'attendance', label: `Attendance (${data.attendance.length})` }, { value: 'bookings', label: `Bookings (${data.bookings.length})` }, { value: 'points', label: `Reward points (${data.ledger.length})` }]} />
      <Card viewAll>
        {tab === 'attendance' && (!data.attendance.length ? <Empty icon={CalendarCheck} title="No attendance in this range" /> : (
          <div className="table-wrap flush" style={{ marginTop: -14 }}>
            <table className="table">
              <thead><tr><th>Date</th><th>Meal</th><th>Response</th><th>Participation</th><th>Confirmed at</th></tr></thead>
              <tbody>{data.attendance.map(a => (
                <tr key={a.date + a.meal_type}><td className="nowrap strong">{prettyDate(a.date)}</td><td>{cap(a.meal_type)}</td>
                  <td>{a.status === 'coming' ? <Badge tone="green" icon={CheckCircle2}>Confirmed</Badge> : <Badge icon={X}>{a.cancelled ? 'Cancelled' : 'Not attending'}</Badge>}</td>
                  <td>{a.arrived ? <Badge tone="blue">Attended</Badge> : <span className="faint small">—</span>}</td>
                  <td className="small muted">{prettyTime(a.updated_at)}</td></tr>
              ))}</tbody>
            </table>
          </div>
        ))}
        {tab === 'bookings' && (!data.bookings.length ? <Empty icon={Clock} title="No bookings in this range" /> : (
          <div className="table-wrap flush" style={{ marginTop: -14 }}>
            <table className="table">
              <thead><tr><th>Date</th><th>Meal</th><th>Slot</th><th>Code</th><th>Status</th></tr></thead>
              <tbody>{data.bookings.map(b => (
                <tr key={b.id}><td className="nowrap strong">{prettyDate(b.date)}</td><td>{cap(b.meal_type)}</td><td>{b.start} – {b.end}</td><td><code>{b.code}</code></td>
                  <td><Badge tone={b.status === 'booked' ? 'green' : b.status === 'served' ? 'blue' : ''}>{b.status === 'served' ? 'Completed' : cap(b.status)}</Badge></td></tr>
              ))}</tbody>
            </table>
          </div>
        ))}
        {tab === 'points' && (!data.ledger.length ? <Empty icon={Gift} title="No points activity in this range" /> : (
          <div className="table-wrap flush" style={{ marginTop: -14 }}>
            <table className="table">
              <thead><tr><th>When</th><th>Activity</th><th className="num">Points</th></tr></thead>
              <tbody>{data.ledger.map(t => (
                <tr key={t.id}><td className="small muted nowrap">{prettyTime(t.created_at)}</td><td>{t.description}</td><td className="num strong" style={{ color: t.points > 0 ? 'var(--good-text)' : undefined }}>{t.points > 0 ? '+' : ''}{t.points}</td></tr>
              ))}</tbody>
            </table>
          </div>
        ))}
      </Card>
    </div>
  )
}
