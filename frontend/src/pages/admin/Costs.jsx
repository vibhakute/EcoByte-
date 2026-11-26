import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { CalendarDays, Coins, IndianRupee } from 'lucide-react'
import { api, useApi } from '../../api'
import { C, Tip, axisProps, barCursor, gridProps, yAxisProps } from '../../components/charts'
import { Badge, Card, Empty, ErrorState, Field, PageHeader, PageLoading, Stat, cap, fmt, inr, kg, prettyDate, useAction } from '../../components/ui'
import { PresetBar, presetRange } from './Analytics'

export default function Costs() {
  const [preset, setPreset] = useState('h25')
  const r = presetRange(preset)
  const { data, error, loading, reload } = useApi('/admin/costs', r)
  const [rates, setRates] = useState(null)
  const [run, busy] = useAction()
  useEffect(() => { if (data && !rates) setRates(data.rates) }, [data, rates])
  if (loading && !data) return <PageLoading />
  if (error) return <ErrorState error={error} onRetry={reload} />
  const s = data.summary

  async function saveRates() {
    const res = await run(() => api('/admin/settings', { method: 'PATCH', body: { cost_breakfast: Number(rates.breakfast), cost_lunch: Number(rates.lunch), cost_dinner: Number(rates.dinner) } }), 'Ingredient cost rates updated')
    if (res) reload(true)
  }

  return (
    <div className="stack">
      <PageHeader title="Waste Cost Tracker" subtitle="The estimated money lost to wasted food, in Indian Rupees." />
      <div className="grid g-4">
        {[['day', 'Daily', 'green'], ['week', 'Weekly', 'blue'], ['month', 'Monthly', 'orange'], ['year', 'Annual', 'purple']].map(([k, l, tone]) => (
          <Stat key={k} tone={tone} icon={k === 'year' ? Coins : CalendarDays} label={`${l} waste cost`} value={s[k]?.waste_cost != null ? inr(s[k].waste_cost) : '₹0'}
            foot={s[k]?.waste_kg != null ? `${kg(s[k].waste_kg)} wasted` : 'No waste recorded'} />
        ))}
      </div>
      <div className="grid g-side">
        <Card title={<><IndianRupee />Cost per kg</>} subtitle="Update with actual ingredient costs for accurate figures">
          <div className="formula">Waste Cost = Waste Quantity (kg) × Cost per kg</div>
          {rates && <div className="stack mt-12" style={{ gap: 10 }}>
            {['breakfast', 'lunch', 'dinner'].map(m => (
              <Field key={m} label={`${cap(m)} (₹/kg)`}><input className="input" type="number" min="1" value={rates[m]} onChange={e => setRates({ ...rates, [m]: e.target.value })} /></Field>
            ))}
            <div><button className="btn primary" disabled={busy} onClick={saveRates}>Save rates</button></div>
            <p className="tiny faint">Each waste entry keeps the rate used at the time, so changing a rate never rewrites past costs. A different rate can also be entered per entry.</p>
          </div>}
        </Card>
        <div className="stack">
          <PresetBar value={preset} onChange={setPreset} />
          <Card title="Cost trend" subtitle={`Total for ${prettyDate(r.start)} – ${prettyDate(r.end)}: ${inr(data.total_cost)}`}>
            {!data.series.length ? <Empty title="No costs in this range" /> : (
              <div className="chart-box"><ResponsiveContainer>
                <BarChart data={data.series} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
                  <CartesianGrid {...gridProps} /><XAxis dataKey="label" {...axisProps} minTickGap={20} />
                  <YAxis {...yAxisProps} width={62} tickFormatter={v => '₹' + fmt(v / 1000) + 'k'} />
                  <Tooltip cursor={barCursor} content={<Tip format={v => inr(v)} extra={x => <div className="tt-row"><span>Waste</span><b>{kg(x.waste_kg)}</b></div>} />} />
                  <Bar isAnimationActive={false} dataKey="waste_cost" name="Waste cost" fill={C.s3} radius={[4, 4, 0, 0]} maxBarSize={34} />
                </BarChart>
              </ResponsiveContainer></div>
            )}
          </Card>
        </div>
      </div>
      <div className="grid g-2">
        <Card viewAll title="Highest-cost meals" subtitle="Food items ranked by total waste cost">
          {!data.costliest_meals.length ? <Empty /> : (
            <table className="table compact flush" style={{ width: 'calc(100% + 44px)' }}>
              <thead><tr><th>Food</th><th className="num">Entries</th><th className="num">Waste</th><th className="num">Avg / entry</th><th className="num">Total cost</th></tr></thead>
              <tbody>{data.costliest_meals.map(x => (
                <tr key={x.meal_type + x.dish}><td><div className="small strong">{x.dish}</div><div className="tiny faint">{cap(x.meal_type)}</div></td>
                  <td className="num">{x.services}</td><td className="num">{kg(x.total_kg)}</td><td className="num">{inr(x.avg_cost)}</td><td className="num strong">{inr(x.total_cost)}</td></tr>
              ))}</tbody>
            </table>
          )}
        </Card>
        <Card viewAll title="Highest-cost days">
          {!data.top_days.length ? <Empty /> : (
            <table className="table compact flush" style={{ width: 'calc(100% + 44px)' }}>
              <thead><tr><th>Date</th><th>Calendar</th><th className="num">Waste</th><th className="num">Cost</th></tr></thead>
              <tbody>{data.top_days.map(x => <tr key={x.date}><td className="nowrap">{prettyDate(x.date, { day: 'numeric', month: 'short', year: 'numeric' })}</td>
                <td>{x.event ? <Badge tone="blue">{x.event}</Badge> : <span className="faint">—</span>}</td><td className="num">{kg(x.waste_kg)}</td><td className="num strong">{inr(x.waste_cost)}</td></tr>)}</tbody>
            </table>
          )}
        </Card>
      </div>
    </div>
  )
}
