import { useEffect, useMemo, useState } from 'react'
import { Check, ChevronLeft, ChevronRight, Lock, X } from 'lucide-react'
import { api, useApi } from '../../api'
import AttendanceCalendar from '../../components/AttendanceCalendar'
import {
  Alert, Badge, Card, Empty, ErrorState, Loading, PageHeader, addDays, cap, mondayOf, prettyDate, prettyTime, todayIso, useToast, Tabs,
} from '../../components/ui'

const MEALS = ['breakfast', 'lunch', 'dinner']

function Toggle({ value, onChange, locked }) {
  if (locked) {
    return (
      <div className="pill-toggle locked" title="Locked">
        {value === 'coming' ? <button className="yes" disabled><Check />Coming</button>
          : value === 'not_coming' ? <button className="no" disabled><X />Not attending</button>
            : <button disabled><Lock />No response</button>}
      </div>
    )
  }
  return (
    <div className="pill-toggle" role="radiogroup">
      <button type="button" role="radio" aria-checked={value === 'coming'} className={value === 'coming' ? 'yes' : ''} onClick={() => onChange('coming')}><Check />Coming</button>
      <button type="button" role="radio" aria-checked={value === 'not_coming'} className={value === 'not_coming' ? 'no' : ''} onClick={() => onChange('not_coming')}><X />No</button>
    </div>
  )
}

function WeeklyPlanner() {
  const thisMonday = mondayOf(todayIso())
  const [week, setWeek] = useState(thisMonday)
  const { data, error, loading, reload } = useApi('/student/attendance', { week_start: week })
  const history = useApi('/student/history')
  const [draft, setDraft] = useState({})
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const toast = useToast()

  useEffect(() => { setDraft({}); setResult(null) }, [week])

  const value = (date, meal) => draft[`${date}|${meal}`] ?? data?.days.find(d => d.date === date)?.meals[meal].status
  const changes = useMemo(() => Object.entries(draft).filter(([k, v]) => {
    const [date, meal] = k.split('|')
    return data?.days.find(d => d.date === date)?.meals[meal].status !== v
  }), [draft, data])

  function setAllOpen(status) {
    const next = { ...draft }
    data.days.filter(d => !d.locked).forEach(d => MEALS.forEach(m => { if (!d.meals[m].closed) next[`${d.date}|${m}`] = status }))
    setDraft(next)
  }

  async function save() {
    setBusy(true)
    try {
      const items = changes.map(([k, status]) => { const [date, meal_type] = k.split('|'); return { date, meal_type, status } })
      const r = await api('/student/attendance', { method: 'POST', body: { items } })
      setResult(r)
      if (r.saved) toast(`Saved ${r.saved} response${r.saved > 1 ? 's' : ''}${r.points_awarded ? ` · +${r.points_awarded} points` : ''}`)
      setDraft({})
      reload(true); history.reload(true)
    } catch (e) { toast(e.message, 'error') } finally { setBusy(false) }
  }

  const openDays = data?.days.filter(d => !d.locked) || []
  return (
    <div className="stack">
      <PageHeader title="Plan your meals"
        subtitle={data ? `Confirm each meal by ${data.deadline_time} the day before. +${data.points_per_confirmation} points per day you answer, +${data.weekly_bonus} for a full week.` : 'Tell the canteen which meals you will eat.'}
        actions={<div className="row">
          <button className="btn icon-btn" aria-label="Previous week" disabled={week <= thisMonday} onClick={() => setWeek(addDays(week, -7))}><ChevronLeft /></button>
          <span className="small strong nowrap" style={{ minWidth: 150, textAlign: 'center' }}>{week === thisMonday ? 'This week' : week === addDays(thisMonday, 7) ? 'Next week' : `Week of ${prettyDate(week)}`}</span>
          <button className="btn icon-btn" aria-label="Next week" disabled={week >= addDays(thisMonday, 7)} onClick={() => setWeek(addDays(week, 7))}><ChevronRight /></button>
        </div>} />

      {result?.errors?.length > 0 && <Alert tone="warn" title="Some responses were not saved:">{result.errors.join(' · ')}</Alert>}

      {error ? <ErrorState error={error} onRetry={reload} /> : (
        <Card title={`${prettyDate(week, { day: 'numeric', month: 'short' })} – ${prettyDate(addDays(week, 6), { day: 'numeric', month: 'short' })}`}
          subtitle={openDays.length ? `${openDays.length} day${openDays.length > 1 ? 's' : ''} still open for changes` : 'All days in this week are locked'}
          actions={openDays.length > 0 && <>
            <button className="btn sm" onClick={() => setAllOpen('coming')}>Mark all coming</button>
            <button className="btn sm ghost" onClick={() => setAllOpen('not_coming')}>Mark all away</button>
          </>} bodyClass="" >
          {loading && !data ? <Loading rows={5} height={44} /> : (
            <div className="week" style={{ margin: '0 -20px -18px' }}>
              {data.days.map(day => (
                <div key={day.date} className={`day-row ${day.closed ? 'closed' : ''} ${day.date === todayIso() ? 'today' : ''}`}>
                  <div className="day-name">
                    <div className="day-date"><span>{day.weekday}</span><b>{Number(day.date.slice(8))}</b></div>
                    <div>
                      <div className="small strong">{prettyDate(day.date, { weekday: 'long' })}</div>
                      <div className="tiny faint">{day.closed ? day.closed_reason : !day.covered ? 'Not covered by your mess pass' : day.locked ? (day.too_far ? 'Opens later' : 'Closed for confirmation') : `Confirm by ${prettyTime(day.deadline)}`}{day.event && !day.closed ? ` · ${day.event}` : ''}</div>
                    </div>
                  </div>
                  {day.closed ? <div className="small faint">Canteen closed</div> : (
                    <div className="meals-row">
                      {MEALS.map(m => (
                        <div className="meal-choice" key={m}>
                          <span className="lbl">{cap(m)}</span>
                          {day.meals[m].closed ? <Badge tone="red" icon={Lock}>Unavailable · {day.meals[m].closed}</Badge> : <Toggle value={value(day.date, m)} locked={day.locked} onChange={v => setDraft({ ...draft, [`${day.date}|${m}`]: v })} />}
                        </div>
                      ))}
                    </div>
                  )}
                  <div>{!day.closed && day.locked && !day.too_far && <Badge icon={Lock}>Closed for confirmation</Badge>}</div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {changes.length > 0 && (
        <div className="card card-pad between" style={{ position: 'sticky', bottom: 76, boxShadow: 'var(--shadow-lg)', zIndex: 20 }}>
          <span className="small"><b>{changes.length}</b> unsaved change{changes.length > 1 ? 's' : ''}</span>
          <div className="row">
            <button className="btn ghost" onClick={() => setDraft({})}>Discard</button>
            <button className="btn primary" onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Save attendance'}</button>
          </div>
        </div>
      )}

      <Card viewAll title="Recent responses" subtitle="Your last confirmations, including changes">
        {history.loading && !history.data ? <Loading /> : !history.data?.attendance?.length ? <Empty title="No responses yet" /> : (
          <div className="table-wrap" style={{ margin: '0 -20px -18px' }}>
            <table className="table">
              <thead><tr><th>Date</th><th>Meal</th><th>Status</th><th>Confirmed</th><th>Last change</th></tr></thead>
              <tbody>
                {history.data.attendance.map(r => (
                  <tr key={`${r.date}${r.meal_type}`}>
                    <td className="nowrap">{prettyDate(r.date)}</td><td>{cap(r.meal_type)}</td>
                    <td>{r.status === 'coming' ? <Badge tone="green">Coming</Badge> : <Badge>{r.cancelled ? 'Cancelled' : 'Not coming'}</Badge>}</td>
                    <td className="small muted nowrap">{prettyTime(r.confirmed_at)}</td>
                    <td className="small muted nowrap">{r.updated_at !== r.confirmed_at ? prettyTime(r.updated_at) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}


export default function StudentAttendance() {
  const [tab, setTab] = useState('plan')
  return (
    <div className="stack">
      <Tabs value={tab} onChange={setTab} options={[{ value: 'plan', label: 'Plan upcoming meals' }, { value: 'history', label: 'Attendance history' }]} />
      {tab === 'plan' ? <WeeklyPlanner /> : <>
        <div className="page-head" style={{ marginBottom: 0 }}><div><h1>Attendance history</h1><p>Recorded attendance from your pass start date, plus upcoming bookings until your pass expires.</p></div></div>
        <AttendanceCalendar path="/student/attendance/calendar" initial="all" />
      </>}
    </div>
  )
}
