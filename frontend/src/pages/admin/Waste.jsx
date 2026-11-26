import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { CalendarDays, Coffee, Moon, Percent, Soup, Trash, Trash2 } from 'lucide-react'
import { api, useApi } from '../../api'
import { C, Legend, MEAL_COLOR, Tip, axisProps, barCursor, gridProps, yAxisProps } from '../../components/charts'
import {
  Alert, Badge, Card, Empty, ErrorState, Field, Loading, PageHeader, Stat, cap, fmt, inr, kg, pct, prettyDate, todayIso, useAction,
} from '../../components/ui'
import { PresetBar, presetRange } from './Analytics'

function WasteForm({ rates, onSaved }) {
  const now = new Date()
  const empty = { date: todayIso(), recorded_at: now.toTimeString().slice(0, 5), meal_type: now.getHours() < 11 ? 'breakfast' : now.getHours() < 17 ? 'lunch' : 'dinner',
    food_name: '', prepared_kg: '', served_kg: '', leftover_kg: '', plate_waste_kg: '', cost_per_kg: '', notes: '' }
  const [f, setF] = useState(empty)
  const [run, busy] = useAction()
  const [msg, setMsg] = useState(null)
  const n = k => (f[k] === '' ? 0 : Number(f[k]))
  const total = n('leftover_kg') + n('plate_waste_kg')
  const rate = f.cost_per_kg ? Number(f.cost_per_kg) : rates?.[f.meal_type]
  const set = k => e => setF({ ...f, [k]: e.target.value })
  const remaining = n('prepared_kg') - n('served_kg')

  async function submit(e) {
    e.preventDefault()
    const r = await run(() => api('/admin/waste', { method: 'POST', body: {
      date: f.date, recorded_at: f.recorded_at || null, meal_type: f.meal_type, food_name: f.food_name, prepared_kg: n('prepared_kg'), served_kg: n('served_kg'),
      leftover_kg: n('leftover_kg'), plate_waste_kg: n('plate_waste_kg'), cost_per_kg: f.cost_per_kg ? Number(f.cost_per_kg) : null, notes: f.notes || null } }), 'Waste entry saved')
    if (r) { setMsg(r.calculation); setF({ ...empty, date: f.date, meal_type: f.meal_type }); onSaved() }
  }
  return (
    <form onSubmit={submit} className="stack" style={{ gap: 14 }}>
      <div className="form-grid">
        <Field label="Meal category"><select className="select" value={f.meal_type} onChange={set('meal_type')}>{['breakfast', 'lunch', 'dinner'].map(m => <option key={m} value={m}>{cap(m)}</option>)}</select></Field>
        <Field label="Food name"><input className="input" value={f.food_name} onChange={set('food_name')} placeholder="e.g. Dal Rice" required minLength={2} /></Field>
        <Field label="Date"><input className="input" type="date" max={todayIso()} value={f.date} onChange={set('date')} required /></Field>
        <Field label="Time"><input className="input" type="time" value={f.recorded_at} onChange={set('recorded_at')} /></Field>
        <Field label="Quantity prepared (kg)"><input className="input" type="number" step="0.1" min="0" value={f.prepared_kg} onChange={set('prepared_kg')} required /></Field>
        <Field label="Quantity served (kg)"><input className="input" type="number" step="0.1" min="0" value={f.served_kg} onChange={set('served_kg')} required /></Field>
        <Field label="Remaining edible food (kg)" hint={f.prepared_kg && f.served_kg ? `Up to ${fmt(Math.max(0, remaining), 1)} kg (prepared − served)` : 'Cooked but not served'}>
          <input className="input" type="number" step="0.1" min="0" value={f.leftover_kg} onChange={set('leftover_kg')} required /></Field>
        <Field label="Plate waste (kg)" hint="Served but not eaten; 0 if not measured"><input className="input" type="number" step="0.1" min="0" value={f.plate_waste_kg} onChange={set('plate_waste_kg')} /></Field>
        <Field label="Cost per kg (₹)" hint={`Default ${cap(f.meal_type)} rate: ₹${rates?.[f.meal_type] ?? '—'}/kg`}><input className="input" type="number" min="1" value={f.cost_per_kg} onChange={set('cost_per_kg')} placeholder={String(rates?.[f.meal_type] ?? '')} /></Field>
        <Field label="Notes"><input className="input" value={f.notes} onChange={set('notes')} placeholder="Optional" /></Field>
      </div>
      <div className="formula">Waste = {fmt(n('leftover_kg'), 1)} + {fmt(n('plate_waste_kg'), 1)} = {fmt(total, 1)} kg · Cost = {fmt(total, 1)} × ₹{rate ?? '—'} = <b>{inr(total * (rate || 0), 2)}</b></div>
      {msg && <Alert tone="success">{msg}</Alert>}
      <div><button className="btn primary" disabled={busy}>{busy ? 'Saving…' : 'Save waste entry'}</button></div>
    </form>
  )
}

export default function Waste() {
  const [preset, setPreset] = useState('30d')
  const [day, setDay] = useState(todayIso())
  const r = presetRange(preset)
  const { data, error, loading, reload } = useApi('/admin/waste', r)
  const entries = useApi('/admin/waste/entries', { date: day })
  const ov = useApi('/admin/overview', { date: todayIso() })
  const costs = useApi('/admin/costs', { start: todayIso(), end: todayIso() })
  const [run] = useAction()
  const refresh = () => { reload(true); entries.reload(true); ov.reload(true) }
  const sum = data?.summary || {}
  const wb = ov.data?.waste?.by_meal || {}

  async function del(e) { if (window.confirm(`Delete the ${e.food_name} entry?`) && await run(() => api(`/admin/waste/${e.id}`, { method: 'DELETE' }), 'Entry deleted')) refresh() }

  return (
    <div className="stack">
      <PageHeader title="Food Waste Monitoring" subtitle="Record actual measurements after each meal: leftover food and plate waste, by food item." />
      <div className="grid g-4">
        <Stat tone="purple" icon={Trash2} label="Today's total waste" value={fmt(ov.data?.waste.total_kg, 1)} unit="kg" foot={ov.data?.waste.pct != null ? `${ov.data.waste.pct}% of food prepared` : 'Waste % appears once prepared kg is logged'} />
        <Stat tone="orange" icon={Coffee} label="Breakfast waste" value={fmt(wb.breakfast?.kg, 1)} unit="kg" foot={inr(wb.breakfast?.cost)} />
        <Stat tone="green" icon={Soup} label="Lunch waste" value={fmt(wb.lunch?.kg, 1)} unit="kg" foot={inr(wb.lunch?.cost)} />
        <Stat tone="blue" icon={Moon} label="Dinner waste" value={fmt(wb.dinner?.kg, 1)} unit="kg" foot={inr(wb.dinner?.cost)} />
      </div>
      <div className="grid g-3">
        <Stat tone="white" icon={CalendarDays} label="This week" value={fmt(sum.week?.waste_kg, 1)} unit="kg" foot={sum.week?.waste_kg != null ? inr(sum.week.waste_cost) : 'No entries yet'} />
        <Stat tone="white" icon={CalendarDays} label="This month" value={fmt(sum.month?.waste_kg, 1)} unit="kg" foot={sum.month?.waste_kg != null ? inr(sum.month.waste_cost) : 'No entries yet'} />
        <Stat tone="white" icon={Percent} label="Waste % this month" value={sum.month?.waste_pct != null ? pct(sum.month.waste_pct) : '—'} foot="waste kg ÷ food prepared kg" />
      </div>

      <div className="grid g-main">
        <Card viewAll title="Entries" subtitle="Each food item measured after the meal"
          actions={<input type="date" className="input sm" style={{ width: 160 }} max={todayIso()} value={day} onChange={e => e.target.value && setDay(e.target.value)} />}>
          {entries.loading && !entries.data ? <Loading /> : !entries.data?.length ? <Empty icon={Trash2} title={`No entries for ${prettyDate(day)}`}>Use the form to record waste after each meal.</Empty> : (
            <div className="table-wrap flush">
              <table className="table compact">
                <thead><tr><th>Time</th><th>Meal</th><th>Food</th><th className="num">Prepared</th><th className="num">Served</th><th className="num">Leftover</th><th className="num">Plate</th><th className="num">Cost</th><th></th></tr></thead>
                <tbody>{entries.data.map(e => (
                  <tr key={e.id}>
                    <td className="small muted nowrap">{e.recorded_at ? e.recorded_at.slice(11, 16) : '—'}</td>
                    <td><span className="row"><i className="dot" style={{ background: MEAL_COLOR[e.meal_type] }} />{cap(e.meal_type)}</span></td>
                    <td className="strong">{e.food_name}{e.synthetic && <> <Badge tone="amber">Synthetic</Badge></>}</td>
                    <td className="num">{kg(e.prepared_kg)}</td><td className="num">{kg(e.served_kg)}</td><td className="num">{kg(e.leftover_kg)}</td><td className="num">{kg(e.plate_kg)}</td>
                    <td className="num strong">{inr(e.waste_cost)}</td>
                    <td className="right">{!e.synthetic && <button className="btn sm ghost icon-btn danger" aria-label="Delete entry" onClick={() => del(e)}><Trash /></button>}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </Card>
        <Card title="Record waste" subtitle="After each meal">
          <WasteForm rates={costs.data?.rates} onSaved={refresh} />
        </Card>
      </div>

      <PresetBar value={preset} onChange={setPreset} />
      {error ? <ErrorState error={error} onRetry={reload} /> : (
        <div className="grid g-2">
          <Card title="Waste by day" subtitle="Leftover vs plate waste" actions={<Legend items={[{ label: 'Leftover', color: C.s1 }, { label: 'Plate waste', color: C.s2 }]} />}>
            {loading && !data ? <div className="skeleton" style={{ height: 280 }} /> : !data.series.length ? <Empty title="No waste records in this range" /> : (
              <div className="chart-box"><ResponsiveContainer>
                <BarChart data={data.series} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid {...gridProps} /><XAxis dataKey="label" {...axisProps} minTickGap={22} /><YAxis {...yAxisProps} />
                  <Tooltip cursor={barCursor} content={<Tip format={v => kg(v)} extra={x => <div className="tt-row"><span>Cost</span><b>{inr(x.waste_cost)}</b></div>} />} />
                  <Bar isAnimationActive={false} dataKey="leftover_kg" name="Leftover" stackId="w" fill={C.s1} stroke="#fff" strokeWidth={1} maxBarSize={22} />
                  <Bar isAnimationActive={false} dataKey="plate_kg" name="Plate waste" stackId="w" fill={C.s2} stroke="#fff" strokeWidth={1} radius={[4, 4, 0, 0]} maxBarSize={22} />
                </BarChart>
              </ResponsiveContainer></div>
            )}
          </Card>
          <Card title="Which meals waste most" subtitle={`${prettyDate(r.start)} – ${prettyDate(r.end)}`}>
            {!data?.by_meal?.length ? <Empty /> : (
              <>
                <div className="chart-box sm"><ResponsiveContainer>
                  <BarChart data={data.by_meal.map(m => ({ ...m, label: cap(m.meal_type) }))} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
                    <CartesianGrid stroke={C.grid} horizontal={false} /><XAxis type="number" {...axisProps} /><YAxis type="category" dataKey="label" {...axisProps} axisLine={false} width={74} />
                    <Tooltip cursor={barCursor} content={<Tip format={v => kg(v)} extra={x => <div className="tt-row"><span>Cost</span><b>{inr(x.waste_cost)}</b></div>} />} />
                    <Bar isAnimationActive={false} dataKey="waste_kg" name="Waste" radius={[0, 4, 4, 0]} maxBarSize={26}
                      shape={p => <rect x={p.x} y={p.y} width={p.width} height={p.height} rx={4} fill={MEAL_COLOR[p.payload.meal_type]} />} />
                  </BarChart>
                </ResponsiveContainer></div>
                <table className="table compact mt-8"><thead><tr><th>Meal</th><th className="num">Leftover</th><th className="num">Plate</th><th className="num">Waste %</th><th className="num">Cost</th></tr></thead>
                  <tbody>{data.by_meal.map(m => <tr key={m.meal_type}><td>{cap(m.meal_type)}</td><td className="num">{kg(m.leftover_kg)}</td><td className="num">{kg(m.plate_kg)}</td><td className="num">{pct(m.waste_pct)}</td><td className="num">{inr(m.waste_cost)}</td></tr>)}</tbody></table>
              </>
            )}
          </Card>
          <Card viewAll title="Highest-waste days" subtitle="Ranked by cost">
            {!data?.top_days?.length ? <Empty /> : (
              <table className="table compact flush" style={{ width: 'calc(100% + 44px)' }}>
                <thead><tr><th>Date</th><th>Note</th><th className="num">Waste</th><th className="num">Cost</th></tr></thead>
                <tbody>{data.top_days.map(x => <tr key={x.date}><td className="nowrap">{prettyDate(x.date, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })}</td><td>{x.event ? <Badge tone="blue">{x.event}</Badge> : <span className="faint">—</span>}</td><td className="num">{kg(x.waste_kg)}</td><td className="num strong">{inr(x.waste_cost)}</td></tr>)}</tbody>
              </table>
            )}
          </Card>
        </div>
      )}
    </div>
  )
}
