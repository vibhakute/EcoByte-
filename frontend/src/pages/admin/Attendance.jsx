import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { CalendarCheck, Check, ChevronLeft, ChevronRight, Clock3, Download, Search, UserCheck, UserX, Users, X } from 'lucide-react'
import { api, download, useApi } from '../../api'
import { Legend, MEAL_COLOR, Tip, axisProps, barCursor, gridProps, yAxisProps } from '../../components/charts'
import {
  Badge, Card, Empty, ErrorState, Field, Loading, PageHeader, Stat, Tabs, addDays, cap, fmt, mondayOf, prettyDate, prettyTime, todayIso, useAction,
} from '../../components/ui'

const MEALS = ['breakfast', 'lunch', 'dinner']

function Status({ x, row, meal, onArrival }) {
  if (!x) return <Badge>Pending</Badge>
  const canArrive = x.status === 'coming' && row.date <= todayIso()
  return (
    <div className="stack" style={{ gap: 3 }}>
      <div className="row" style={{ gap: 4 }}>
        {x.status === 'coming' ? <Badge tone="green" icon={Check}>Coming</Badge> : <Badge icon={X}>{x.cancelled ? 'Cancelled' : 'Not coming'}</Badge>}
        {canArrive && (
          <button className={`btn sm ${x.arrived ? 'soft' : 'ghost'}`} style={{ height: 22, padding: '0 6px', fontSize: 11 }} title="Toggle arrival"
            onClick={() => onArrival(row, meal, !x.arrived)}>{x.arrived ? 'Arrived ✓' : 'Mark arrived'}</button>
        )}
      </div>
      <span className="tiny faint">{prettyTime(x.updated_at)}</span>
    </div>
  )
}

function Records() {
  const [f, setF] = useState({ start: addDays(todayIso(), -7), end: addDays(todayIso(), 7), q: '', meal: '', status: '' })
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  useEffect(() => { const t = setTimeout(() => { setF(x => ({ ...x, q })); setPage(1) }, 300); return () => clearTimeout(t) }, [q])
  const { data, error, loading, reload } = useApi('/admin/attendance/records', { ...f, page, size: 25 })
  const [run, busy] = useAction()
  const pages = data ? Math.max(1, Math.ceil(data.total / data.size)) : 1
  async function arrival(row, meal, arrived) {
    if (await run(() => api('/admin/attendance/arrival', { method: 'POST', body: { user_id: row.user_id, date: row.date, meal_type: meal, arrived } }), arrived ? 'Marked as arrived' : 'Arrival removed')) reload(true)
  }
  return (
    <Card viewAll title="Attendance records" subtitle="Every confirmation with its timestamp. Mark arrivals at the counter to track no-shows."
      actions={<button className="btn sm" disabled={busy} onClick={() => run(() => download('/admin/reports/attendance', { start: f.start, end: f.end, q: f.q }, `EcoByte_Attendance_${f.start}_${f.end}.xlsx`), 'Attendance report downloaded')}><Download />Download report</button>}>
      <div className="row wrap" style={{ gap: 12, alignItems: 'flex-end', marginBottom: 14 }}>
        <div className="search" style={{ maxWidth: 260 }}><Search /><input placeholder="Name or student ID" value={q} onChange={e => setQ(e.target.value)} aria-label="Search students" /></div>
        <Field label="From"><input type="date" className="input sm" value={f.start} onChange={e => { setF({ ...f, start: e.target.value }); setPage(1) }} /></Field>
        <Field label="To"><input type="date" className="input sm" value={f.end} onChange={e => { setF({ ...f, end: e.target.value }); setPage(1) }} /></Field>
        <Field label="Meal"><select className="select sm" value={f.meal} onChange={e => setF({ ...f, meal: e.target.value })}><option value="">All</option>{MEALS.map(m => <option key={m} value={m}>{cap(m)}</option>)}</select></Field>
        <Field label="Status"><select className="select sm" value={f.status} onChange={e => setF({ ...f, status: e.target.value })}><option value="">All</option><option value="coming">Coming</option><option value="not_coming">Not coming</option></select></Field>
      </div>
      {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Loading rows={6} /> : !data.items.length ? (
        <Empty icon={CalendarCheck} title="No confirmations in this range">Records appear here as soon as students tick their attendance.</Empty>
      ) : <>
        <div className="table-wrap flush" style={{ marginBottom: 0 }}>
          <table className="table">
            <thead><tr><th>Student</th><th>Student ID</th><th>Date</th>{MEALS.map(m => <th key={m}>{cap(m)}</th>)}</tr></thead>
            <tbody>{data.items.map(r => (
              <tr key={r.date + r.user_id}>
                <td className="strong">{r.name}</td><td className="small">{r.student_code}</td>
                <td className="nowrap">{prettyDate(r.date)}</td>
                {MEALS.map(m => <td key={m}><Status x={r.meals[m]} row={r} meal={m} onArrival={arrival} /></td>)}
              </tr>
            ))}</tbody>
          </table>
        </div>
        <div className="between mt-16"><span className="small muted">{data.total} records · page {page} of {pages}</span>
          <div className="row"><button className="btn sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button><button className="btn sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</button></div></div>
      </>}
    </Card>
  )
}

function Weekly() {
  const [week, setWeek] = useState(mondayOf(todayIso()))
  const { data, error, loading, reload } = useApi('/admin/attendance', { week_start: week })
  if (loading && !data) return <Loading rows={5} />
  if (error) return <ErrorState error={error} onRetry={reload} />
  const chart = data.days.map(d => ({ label: prettyDate(d.date, { weekday: 'short', day: 'numeric' }), ...Object.fromEntries(MEALS.map(m => [m, d.closed ? null : d.meals[m].coming])) }))
  return (
    <Card title="Weekly confirmations" subtitle={`${prettyDate(week, { day: 'numeric', month: 'short' })} – ${prettyDate(addDays(week, 6), { day: 'numeric', month: 'short' })} · ${data.registered} registered students`}
      actions={<div className="row"><button className="btn sm icon-btn" aria-label="Previous week" onClick={() => setWeek(addDays(week, -7))}><ChevronLeft /></button>
        <button className="btn sm" onClick={() => setWeek(mondayOf(todayIso()))}>This week</button>
        <button className="btn sm icon-btn" aria-label="Next week" onClick={() => setWeek(addDays(week, 7))}><ChevronRight /></button></div>}>
      <div className="between" style={{ marginBottom: 8 }}><span /><Legend items={MEALS.map(m => ({ label: cap(m), color: MEAL_COLOR[m] }))} /></div>
      <div className="chart-box sm"><ResponsiveContainer>
        <BarChart data={chart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barGap={2}>
          <CartesianGrid {...gridProps} /><XAxis dataKey="label" {...axisProps} /><YAxis {...yAxisProps} allowDecimals={false} />
          <Tooltip cursor={barCursor} content={<Tip />} />
          {MEALS.map(m => <Bar isAnimationActive={false} key={m} dataKey={m} name={cap(m)} fill={MEAL_COLOR[m]} radius={[4, 4, 0, 0]} maxBarSize={18} />)}
        </BarChart>
      </ResponsiveContainer></div>
      <div className="table-wrap flush mt-16">
        <table className="table compact">
          <thead><tr><th>Day</th>{MEALS.map(m => <th key={m} className="num">{cap(m)}<div className="tiny faint" style={{ fontWeight: 400 }}>coming · no · pending · arrived</div></th>)}</tr></thead>
          <tbody>{data.days.map(d => (
            <tr key={d.date}><td className="nowrap strong">{prettyDate(d.date)}</td>
              {d.closed ? <td colSpan={3} className="faint">Closed · {d.closed_reason}</td> : MEALS.map(m => {
                const x = d.meals[m]
                return <td key={m} className="num nowrap"><b>{x.coming}</b> <span className="faint">· {x.not_coming} · {x.pending} · </span>{x.arrived}</td>
              })}</tr>
          ))}</tbody>
        </table>
      </div>
    </Card>
  )
}

function NoShows() {
  const { data, loading } = useApi('/admin/attendance/no-shows')
  if (loading && !data) return <Loading />
  return (
    <Card viewAll title="Confirmed but did not arrive" subtitle="Last 14 days. Only meals where arrivals were recorded (Mark arrived / booking marked served) are checked.">
      {!data.tracked_services ? <Empty icon={UserX} title="No arrival records yet">Mark arrivals in the records table, or mark slot bookings as served, to see no-shows here.</Empty>
        : !data.items.length ? <Empty icon={UserCheck} title="No no-shows">Everyone who confirmed for tracked meals arrived.</Empty> : (
          <table className="table flush" style={{ width: 'calc(100% + 44px)' }}>
            <thead><tr><th>Date</th><th>Meal</th><th>Student</th><th>Student ID</th><th>Confirmed at</th></tr></thead>
            <tbody>{data.items.map(x => <tr key={x.date + x.meal_type + x.user_id}><td>{prettyDate(x.date)}</td><td>{cap(x.meal_type)}</td><td className="strong">{x.name}</td><td>{x.student_code}</td><td className="small muted">{prettyTime(x.confirmed_at)}</td></tr>)}</tbody>
          </table>
        )}
    </Card>
  )
}

function Roll() {
  const [f, setF] = useState({ date: todayIso(), meal: new Date().getHours() < 11 ? 'breakfast' : new Date().getHours() < 17 ? 'lunch' : 'dinner', q: '' })
  const { data, error, loading, reload } = useApi('/admin/attendance/roll', { date: f.date, meal: f.meal, q: f.q })
  const [run, busy] = useAction()
  const mark = async (ids, present, msg) => {
    if (!ids.length) return
    if (await run(() => api('/admin/attendance/mark', { method: 'POST', body: { user_ids: ids, date: f.date, meal_type: f.meal, present } }), msg)) reload(true)
  }
  const rows = data?.rows || []
  const t = data?.totals
  return (
    <Card title="Record attendance" subtitle="Tick students as they are served. This is the official attendance record (bookings alone never count) and earns attendance tokens."
      actions={<div className="row wrap">
        <input type="date" className="input sm" style={{ width: 150 }} max={todayIso()} value={f.date} onChange={e => e.target.value && setF({ ...f, date: e.target.value })} />
        <div className="seg">{MEALS.map(m => <button key={m} className={f.meal === m ? 'on' : ''} onClick={() => setF({ ...f, meal: m })}>{cap(m)}</button>)}</div>
      </div>}>
      {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Loading rows={6} /> : data.closed ? (
        <Empty icon={CalendarCheck} title={`${cap(f.meal)} was closed`}>{data.closed}</Empty>
      ) : <>
        <div className="row wrap" style={{ gap: 18, marginBottom: 12 }}>
          <span className="small">Eligible: <b>{t.eligible}</b></span><span className="small">Planned: <b>{t.planned}</b></span>
          <span className="small">Booked: <b>{t.booked}</b></span><span className="small">Present: <b className="green">{t.present}</b></span>
          <div style={{ flex: 1 }} />
          <div className="search" style={{ maxWidth: 220 }}><Search /><input placeholder="Find student" value={f.q} onChange={e => setF({ ...f, q: e.target.value })} aria-label="Find student" /></div>
          <button className="btn sm soft" disabled={busy} onClick={() => mark(rows.filter(r => r.booking && !r.present).map(r => r.user_id), true, 'Booked students marked present')}>Mark all booked present</button>
        </div>
        {!rows.length ? <Empty icon={Users} title="No students with a valid pass for this date" /> : (
          <div className="table-wrap flush">
            <table className="table">
              <thead><tr><th style={{ width: 70 }}>Present</th><th>Student</th><th>Plan</th><th>Booking</th><th>Recorded</th></tr></thead>
              <tbody>{rows.map(r => (
                <tr key={r.user_id} style={{ background: r.present ? 'var(--brand-50)' : undefined }}>
                  <td><input type="checkbox" style={{ width: 20, height: 20, accentColor: 'var(--brand)' }} checked={r.present} disabled={busy}
                    onChange={e => mark([r.user_id], e.target.checked, e.target.checked ? `${r.name} marked present` : `${r.name} unmarked`)} aria-label={`${r.name} present`} /></td>
                  <td><div className="strong">{r.name}</div><div className="tiny faint">{r.student_code}{!r.has_pass && ' · no valid pass'}</div></td>
                  <td>{r.plan === 'coming' ? <Badge tone="green">Coming</Badge> : r.plan === 'not_coming' ? <Badge>Not attending</Badge> : <span className="faint small">—</span>}</td>
                  <td>{r.booking ? <span className="small">{r.booking.time} · <code>{r.booking.code}</code></span> : <span className="faint small">—</span>}</td>
                  <td className="small muted">{r.recorded_at ? prettyTime(r.recorded_at) : '—'}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </>}
    </Card>
  )
}

export default function AdminAttendance() {
  const [tab, setTab] = useState('roll')
  const ov = useApi('/admin/overview', { date: todayIso() })
  const a = ov.data?.attendance
  return (
    <div className="stack">
      <PageHeader title="Attendance Management" subtitle="Record actual attendance at the counter, and review advance confirmations that drive the demand forecast." />
      <div className="grid g-4">
        <Stat tone="green" icon={Users} label="Registered students" value={fmt(a?.registered)} loading={!a} />
        <Stat tone="blue" icon={UserCheck} label="Confirmed today" value={fmt(a?.confirmed_students)} loading={!a} foot={a ? `${a.attendance_pct}% of students` : ''} />
        <Stat tone="orange" icon={UserX} label="Not attending today" value={fmt(a?.absent_students)} loading={!a} />
        <Stat tone="purple" icon={Clock3} label="No response yet" value={fmt(a?.pending_students)} loading={!a} />
      </div>
      <Tabs value={tab} onChange={setTab} options={[{ value: 'roll', label: 'Record attendance' }, { value: 'records', label: 'Confirmations' }, { value: 'week', label: 'Weekly summary' }, { value: 'noshow', label: 'No-shows' }]} />
      {tab === 'roll' ? <Roll /> : tab === 'records' ? <Records /> : tab === 'week' ? <Weekly /> : <NoShows />}
    </div>
  )
}
