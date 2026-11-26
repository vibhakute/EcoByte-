import { useEffect, useState } from 'react'
import { CalendarPlus, Trash } from 'lucide-react'
import { api, useApi } from '../../api'
import { Badge, Card, Empty, ErrorState, Field, Loading, PageHeader, PageLoading, Seg, cap, prettyDate, todayIso, useAction } from '../../components/ui'

const NUM = ['buffer_pct', 'attendance_window_days', 'points_per_confirmation', 'weekly_streak_bonus', 'cost_per_kg', 'cost_breakfast',
  'cost_lunch', 'cost_dinner', 'booking_cancel_minutes', 'baseline_manual_daily', 'tokens_per_attended_meal', 'coupon_validity_days',
  'expiring_soon_days', 'price_monthly', 'price_six_month']

export default function Settings() {
  const { data, error, loading, reload } = useApi('/admin/settings')
  const events = useApi('/admin/events')
  const [f, setF] = useState(null)
  const [ev, setEv] = useState({ date: todayIso(), kind: 'event', name: '', canteen_closed: false })
  const [run, busy] = useAction()
  useEffect(() => { if (data) setF(data) }, [data])
  if (loading && !data) return <PageLoading />
  if (error) return <ErrorState error={error} onRetry={reload} />
  if (!f) return null
  const set = k => e => setF({ ...f, [k]: e.target.value })

  async function save(e) {
    e.preventDefault()
    const body = { ...f }
    NUM.forEach(k => { body[k] = Number(body[k]) })
    delete body.active_model
    const r = await run(() => api('/admin/settings', { method: 'PATCH', body }), 'Settings saved')
    if (r) setF(r)
  }
  async function addEvent(e) {
    e.preventDefault()
    if (await run(() => api('/admin/events', { method: 'POST', body: ev }), 'Calendar entry added')) { setEv({ ...ev, name: '' }); events.reload(true) }
  }
  async function delEvent(x) { if (window.confirm(`Delete ${x.name} on ${x.date}?`) && await run(() => api(`/admin/events/${x.id}`, { method: 'DELETE' }), 'Deleted')) events.reload(true) }

  return (
    <div className="stack">
      <PageHeader title="Settings" subtitle="Parameters used by forecasts, attendance, rewards, bookings, costs and donations." />
      <form onSubmit={save} className="stack">
        <div className="grid g-2">
          <Card title="Canteen & donations">
            <div className="form-grid">
              <Field label="Canteen name" className="span-all"><input className="input" value={f.canteen_name} onChange={set('canteen_name')} /></Field>
              <Field label="Default pickup location" className="span-all"><input className="input" value={f.pickup_location} onChange={set('pickup_location')} /></Field>
              <Field label="Public web address" className="span-all" hint="Used in NGO links, e.g. https://ecobyte.yourcollege.edu. Leave blank to use this browser's address (only works for NGOs if the site is reachable from their phones).">
                <input className="input" value={f.public_base_url} onChange={set('public_base_url')} placeholder="https://…" /></Field>
            </div>
          </Card>
          <Card title="Meal demand forecast">
            <div className="stack">
              <Field label="Forecast mode">
                <Seg value={f.forecast_mode} onChange={v => setF({ ...f, forecast_mode: v })} options={[{ value: 'confirmations', label: 'Confirmations (starts at 0)' }, { value: 'hybrid', label: 'Hybrid (history + confirmations)' }]} />
              </Field>
              <p className="small muted">{f.forecast_mode === 'confirmations'
                ? 'Predicted demand = confirmed students × turnout ratio learned from your recorded services (1.0 until 5 services are recorded).'
                : 'Uses same-weekday history, trend, menu and calendar, blended with live confirmations. Best once you have a year of real records.'}</p>
              <Field label="Preparation buffer (%)" hint="Recommended = predicted + buffer (rounded up)"><input className="input" type="number" step="0.5" min="0" max="50" value={f.buffer_pct} onChange={set('buffer_pct')} /></Field>
            </div>
          </Card>
          <Card title="Attendance & slot booking">
            <div className="form-grid">
              <Field label="Daily deadline" hint="Confirm by this time the day before"><input className="input" type="time" value={f.attendance_deadline} onChange={set('attendance_deadline')} /></Field>
              <Field label="Confirmation window (days)"><input className="input" type="number" min="1" max="31" value={f.attendance_window_days} onChange={set('attendance_window_days')} /></Field>
              <Field label="Booking / change / cancel deadline (min)" hint="Minutes before the slot starts; bookings lock after this"><input className="input" type="number" min="0" value={f.booking_cancel_minutes} onChange={set('booking_cancel_minutes')} /></Field>
            </div>
          </Card>
          <Card title="Reward tokens & coupons">
            <div className="form-grid">
              <Field label="Tokens per attended meal" hint="Verified attendance only"><input className="input" type="number" min="0" value={f.tokens_per_attended_meal} onChange={set('tokens_per_attended_meal')} /></Field>
              <Field label="Tokens per planned day"><input className="input" type="number" min="0" value={f.points_per_confirmation} onChange={set('points_per_confirmation')} /></Field>
              <Field label="Full-week planning bonus"><input className="input" type="number" min="0" value={f.weekly_streak_bonus} onChange={set('weekly_streak_bonus')} /></Field>
              <Field label="Coupon validity (days)"><input className="input" type="number" min="1" value={f.coupon_validity_days} onChange={set('coupon_validity_days')} /></Field>
            </div>
          </Card>
          <Card title="Mess passes">
            <div className="form-grid">
              <Field label="Monthly pass price (₹)" hint="30 days"><input className="input" type="number" min="0" value={f.price_monthly} onChange={set('price_monthly')} /></Field>
              <Field label="Six-month pass price (₹)" hint="180 days"><input className="input" type="number" min="0" value={f.price_six_month} onChange={set('price_six_month')} /></Field>
              <Field label="“Expiring soon” threshold (days)"><input className="input" type="number" min="1" max="30" value={f.expiring_soon_days} onChange={set('expiring_soon_days')} /></Field>
              <label className="check span-all"><input type="checkbox" checked={!!f.holiday_extends_pass} onChange={e => setF({ ...f, holiday_extends_pass: e.target.checked })} />
                <span>Extend active passes by 1 day for each published <b>full-day</b> holiday (otherwise holidays don't change pass validity)</span></label>
            </div>
          </Card>
          <Card title="Ingredient cost per kg (₹)">
            <div className="form-grid three">
              <Field label="Breakfast"><input className="input" type="number" min="1" value={f.cost_breakfast} onChange={set('cost_breakfast')} /></Field>
              <Field label="Lunch"><input className="input" type="number" min="1" value={f.cost_lunch} onChange={set('cost_lunch')} /></Field>
              <Field label="Dinner"><input className="input" type="number" min="1" value={f.cost_dinner} onChange={set('cost_dinner')} /></Field>
            </div>
          </Card>
          <Card title="Savings baseline">
            <div className="stack">
              <Seg value={f.baseline_mode} onChange={v => setF({ ...f, baseline_mode: v })} options={[{ value: 'period', label: 'Historical period' }, { value: 'manual', label: 'Manual value' }]} />
              {f.baseline_mode === 'period' ? (
                <div className="form-grid">
                  <Field label="Baseline from"><input className="input" type="date" value={f.baseline_start} onChange={set('baseline_start')} /></Field>
                  <Field label="Baseline to"><input className="input" type="date" value={f.baseline_end} onChange={set('baseline_end')} /></Field>
                </div>
              ) : <Field label="Baseline waste cost per operating day (₹)"><input className="input" type="number" min="0" value={f.baseline_manual_daily} onChange={set('baseline_manual_daily')} /></Field>}
            </div>
          </Card>
        </div>
        <div className="row"><button className="btn primary" disabled={busy}>Save settings</button><button type="button" className="btn ghost" onClick={() => setF(data)}>Reset</button></div>
      </form>

      <Card viewAll title="College calendar" subtitle="Holidays, vacations, exams and events. Closed days block attendance and bookings.">
        <form className="row wrap" style={{ alignItems: 'flex-end', gap: 12 }} onSubmit={addEvent}>
          <Field label="Date"><input className="input sm" type="date" value={ev.date} onChange={e => setEv({ ...ev, date: e.target.value })} required /></Field>
          <Field label="Type"><select className="select sm" value={ev.kind} onChange={e => setEv({ ...ev, kind: e.target.value })}>{['holiday', 'vacation', 'exam', 'event'].map(k => <option key={k} value={k}>{cap(k)}</option>)}</select></Field>
          <Field label="Name"><input className="input sm" value={ev.name} onChange={e => setEv({ ...ev, name: e.target.value })} placeholder="e.g. Cultural fest" required minLength={2} /></Field>
          <label className="check" style={{ marginBottom: 6 }}><input type="checkbox" checked={ev.canteen_closed} onChange={e => setEv({ ...ev, canteen_closed: e.target.checked })} />Canteen closed</label>
          <button className="btn" disabled={busy}><CalendarPlus />Add</button>
        </form>
        <div className="mt-16">
          {events.loading && !events.data ? <Loading /> : !events.data?.length ? <Empty title="No upcoming calendar entries" /> : (
            <div className="table-wrap flush" style={{ maxHeight: 340, overflowY: 'auto' }}>
              <table className="table compact">
                <thead><tr><th>Date</th><th>Name</th><th>Type</th><th>Canteen</th><th></th></tr></thead>
                <tbody>{events.data.map(x => (
                  <tr key={x.id}><td className="nowrap">{prettyDate(x.date)}</td><td className="small strong">{x.name}</td><td><Badge tone="blue">{cap(x.kind)}</Badge></td>
                    <td>{x.canteen_closed ? <Badge tone="red">Closed</Badge> : <Badge tone="green">Open</Badge>}</td>
                    <td className="right"><button className="btn sm ghost icon-btn" aria-label="Delete" onClick={() => delEvent(x)}><Trash size={14} /></button></td></tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}
