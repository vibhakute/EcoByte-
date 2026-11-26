import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { BrainCircuit, Play } from 'lucide-react'
import { api, useApi } from '../../api'
import { C, Legend, MEAL_COLOR, Tip, axisProps, barCursor, cursor, gridProps, yAxisProps } from '../../components/charts'
import {
  Alert, Card, Empty, ErrorState, Field, PageHeader, PageLoading, Seg, addDays, cap, fmt, inr, kg, pct, prettyDate, prettyTime, todayIso, useAction,
} from '../../components/ui'

export const PRESETS = [
  { value: '7d', label: 'Last 7 days', days: 7, gran: 'day' },
  { value: '30d', label: 'Last 30 days', days: 30, gran: 'day' },
  { value: '3m', label: 'Last 3 months', days: 91, gran: 'week' },
  { value: '6m', label: 'Last 6 months', days: 182, gran: 'week' },
  { value: '1y', label: 'Last year', days: 365, gran: 'month' },
  { value: 'h25', label: '2025 history', start: '2025-01-01', end: '2025-12-31', gran: 'month' },
]
export const presetRange = v => {
  const p = PRESETS.find(x => x.value === v)
  return p.start ? { start: p.start, end: p.end, granularity: p.gran } : { start: addDays(todayIso(), -p.days), end: todayIso(), granularity: p.gran }
}

export function PresetBar({ value, onChange, children }) {
  return (
    <div className="card card-pad row wrap" style={{ gap: 12, justifyContent: 'space-between' }}>
      <Seg value={value} onChange={onChange} options={PRESETS.map(p => ({ value: p.value, label: p.label }))} />
      {children}
    </div>
  )
}

function ChartCard({ title, subtitle, legend, children, empty }) {
  return (
    <Card title={title} subtitle={subtitle} actions={legend && <Legend items={legend} />}>
      {empty ? <Empty title="No data in this range">Choose a longer range or “2025 history”.</Empty> : <div className="chart-box">{children}</div>}
    </Card>
  )
}

const line = (key, name, color, dash) => <Line isAnimationActive={false} dataKey={key} name={name} stroke={color} strokeWidth={2} strokeDasharray={dash} dot={false} activeDot={{ r: 4, stroke: '#fff', strokeWidth: 2 }} connectNulls />
const bar = (key, name, color, stack, top = true) => <Bar isAnimationActive={false} dataKey={key} name={name} fill={color} stackId={stack} radius={top ? [4, 4, 0, 0] : 0} maxBarSize={26} stroke={stack ? '#fff' : undefined} strokeWidth={stack ? 1 : 0} />

function ModelCard() {
  const { data, reload } = useApi('/admin/model')
  const [run, busy] = useAction()
  if (!data) return null
  const ev = data.history_backtest
  const last = data.runs[0]
  return (
    <Card title={<><BrainCircuit />Prediction model (history-based)</>} subtitle="Evaluated on the imported historical data; used for preparation only in hybrid mode (Settings)."
      actions={<button className="btn sm" disabled={busy} onClick={async () => { if (await run(() => api('/admin/model/train', { method: 'POST' }), 'Random forest trained and evaluated')) reload() }}><Play />{busy ? 'Training…' : last ? 'Retrain random forest' : 'Train random forest'}</button>}>
      <div className="grid g-2">
        <div>
          <div className="small strong">Baseline (same-weekday × trend × menu × calendar)</div>
          {ev.available ? <dl className="kv mt-8">
            <dt>Walk-forward test window</dt><dd>{prettyDate(ev.test_start)} – {prettyDate(ev.test_end)}</dd>
            <dt>MAE per service</dt><dd>{fmt(ev.overall.mae, 1)} meals</dd>
            <dt>MAPE per service</dt><dd>{pct(ev.overall.mape)}</dd>
            <dt>Services tested</dt><dd>{ev.overall.n}</dd>
          </dl> : <p className="small muted mt-8">Needs at least 120 operating days of history.</p>}
        </div>
        <div>
          <div className="small strong">Random forest regression</div>
          {!last ? <p className="small muted mt-8">Not trained. Nothing is claimed until you train it here.</p> : <>
            <dl className="kv mt-8">
              <dt>Trained</dt><dd>{prettyTime(last.trained_at)}</dd>
              <dt>MAE / MAPE (hold-out)</dt><dd>{fmt(last.mae, 1)} · {pct(last.mape)}</dd>
              <dt>Baseline on same hold-out</dt><dd>{fmt(last.baseline_mae, 1)} · {pct(last.baseline_mape)}</dd>
            </dl>
            <div className="mt-8">{last.mae > last.baseline_mae ? <Alert tone="info">Baseline is more accurate on this data, so keep the baseline.</Alert> : <Alert tone="success">Random forest beats the baseline on held-out data.</Alert>}</div>
          </>}
        </div>
      </div>
      <p className="tiny faint mt-12">Synthetic data warning: these accuracy figures describe the demonstration dataset, not your canteen.</p>
    </Card>
  )
}

export default function Analytics() {
  const [preset, setPreset] = useState('h25')
  const [meal, setMeal] = useState('')
  const r = presetRange(preset)
  const { data, error, loading, reload } = useApi('/admin/analytics', { ...r, meal })
  const weekly = useApi('/admin/analytics', { ...r, granularity: 'week', meal })
  const daily = useApi('/admin/analytics', { ...r, granularity: preset === 'h25' || preset === '1y' ? 'week' : 'day', meal })

  return (
    <div className="stack">
      <PageHeader title="Analytics" subtitle="Trends from stored records: imported history plus everything recorded in EcoByte." />
      <PresetBar value={preset} onChange={setPreset}>
        <Field label=""><select className="select sm" value={meal} onChange={e => setMeal(e.target.value)} aria-label="Meal filter">
          <option value="">All meals</option>{['breakfast', 'lunch', 'dinner'].map(m => <option key={m} value={m}>{cap(m)}</option>)}</select></Field>
      </PresetBar>
      {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <PageLoading /> : (() => {
        const s = data.series
        const empty = !s.length
        const ds = daily.data?.series || []
        const ws = weekly.data?.series || []
        return (
          <>
            {empty && <Alert tone="info">No records between {prettyDate(r.start)} and {prettyDate(r.end)} yet. Live records appear here once you record services; try “2025 history”.</Alert>}
            <div className="grid g-2">
              <ChartCard title="1. Daily student attendance trend" subtitle={preset === 'h25' || preset === '1y' ? 'Weekly totals (long range)' : 'Total attendance per day'} empty={!ds.length}
                legend={[{ label: 'Attendance', color: C.s1, kind: 'line' }, { label: 'Confirmations', color: C.s2, kind: 'line' }]}>
                <ResponsiveContainer><LineChart data={ds} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
                  <CartesianGrid {...gridProps} /><XAxis dataKey="label" {...axisProps} minTickGap={24} /><YAxis {...yAxisProps} width={54} />
                  <Tooltip cursor={cursor} content={<Tip />} />{line('att', 'Attendance', C.s1)}{line('conf', 'Confirmations', C.s2)}
                </LineChart></ResponsiveContainer>
              </ChartCard>
              <ChartCard title="2. Weekly attendance comparison" subtitle="Total attendance per week" empty={!ws.length}>
                <ResponsiveContainer><BarChart data={ws} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
                  <CartesianGrid {...gridProps} /><XAxis dataKey="label" {...axisProps} minTickGap={24} /><YAxis {...yAxisProps} width={54} />
                  <Tooltip cursor={barCursor} content={<Tip />} />{bar('att', 'Attendance', C.s1)}
                </BarChart></ResponsiveContainer>
              </ChartCard>
              <ChartCard title="3. Breakfast, lunch & dinner demand" subtitle="Average attendance per service" empty={!data.meal_split.length}>
                <ResponsiveContainer><BarChart data={data.meal_split.map(m => ({ ...m, label: cap(m.meal_type) }))} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
                  <CartesianGrid {...gridProps} /><XAxis dataKey="label" {...axisProps} /><YAxis {...yAxisProps} />
                  <Tooltip cursor={barCursor} content={<Tip extra={x => <div className="tt-row"><span>Total</span><b>{fmt(x.total)}</b></div>} />} />
                  <Bar isAnimationActive={false} dataKey="avg_attendance" name="Avg attendance" radius={[4, 4, 0, 0]} maxBarSize={60}
                    shape={p => <rect x={p.x} y={p.y} width={p.width} height={p.height} rx={4} fill={MEAL_COLOR[p.payload.meal_type]} />} />
                </BarChart></ResponsiveContainer>
              </ChartCard>
              <ChartCard title="4. Predicted vs actual demand" subtitle="Using the prediction frozen before each service" empty={!data.actual_vs_predicted.length}
                legend={[{ label: 'Actual', color: C.s1, kind: 'line' }, { label: 'Predicted', color: C.s2, kind: 'dash' }]}>
                <ResponsiveContainer><LineChart data={data.actual_vs_predicted} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
                  <CartesianGrid {...gridProps} /><XAxis dataKey="label" {...axisProps} minTickGap={24} /><YAxis {...yAxisProps} />
                  <Tooltip cursor={cursor} content={<Tip />} />{line('actual', 'Actual', C.s1)}{line('predicted', 'Predicted', C.s2, '5 4')}
                </LineChart></ResponsiveContainer>
              </ChartCard>
              <ChartCard title="5. Meals prepared vs served" empty={empty} legend={[{ label: 'Prepared', color: C.s2 }, { label: 'Served', color: C.s1 }]}>
                <ResponsiveContainer><BarChart data={s} margin={{ top: 8, right: 8, left: 4, bottom: 0 }} barGap={2}>
                  <CartesianGrid {...gridProps} /><XAxis dataKey="label" {...axisProps} minTickGap={24} /><YAxis {...yAxisProps} width={54} />
                  <Tooltip cursor={barCursor} content={<Tip extra={x => <div className="tt-row"><span>Not served</span><b>{fmt(x.prepared - x.served)}</b></div>} />} />
                  {bar('prepared', 'Prepared', C.s2)}{bar('served', 'Served', C.s1)}
                </BarChart></ResponsiveContainer>
              </ChartCard>
              <ChartCard title="6. Weekly & monthly food waste" subtitle="Leftover (cooked, not served) vs plate waste" empty={empty}
                legend={[{ label: 'Leftover', color: C.s1 }, { label: 'Plate waste', color: C.s2 }]}>
                <ResponsiveContainer><BarChart data={s} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
                  <CartesianGrid {...gridProps} /><XAxis dataKey="label" {...axisProps} minTickGap={24} /><YAxis {...yAxisProps} width={54} />
                  <Tooltip cursor={barCursor} content={<Tip format={v => kg(v)} extra={x => <div className="tt-row"><span>Waste %</span><b>{pct(x.waste_pct)}</b></div>} />} />
                  {bar('leftover_kg', 'Leftover', C.s1, 'w', false)}{bar('plate_kg', 'Plate waste', C.s2, 'w')}
                </BarChart></ResponsiveContainer>
              </ChartCard>
              <ChartCard title="7. Food consumption pattern by weekday" subtitle="Average attendance per service (vacations excluded)" empty={!data.weekday.length}
                legend={['breakfast', 'lunch', 'dinner'].filter(m => !meal || m === meal).map(m => ({ label: cap(m), color: MEAL_COLOR[m] }))}>
                <ResponsiveContainer><BarChart data={data.weekday} margin={{ top: 8, right: 8, left: 4, bottom: 0 }} barGap={2}>
                  <CartesianGrid {...gridProps} /><XAxis dataKey="weekday" {...axisProps} /><YAxis {...yAxisProps} />
                  <Tooltip cursor={barCursor} content={<Tip />} />
                  {['breakfast', 'lunch', 'dinner'].filter(m => !meal || m === meal).map(m => <Bar isAnimationActive={false} key={m} dataKey={m} name={cap(m)} fill={MEAL_COLOR[m]} radius={[4, 4, 0, 0]} maxBarSize={18} />)}
                </BarChart></ResponsiveContainer>
              </ChartCard>
              <ChartCard title="8. Waste cost trend" subtitle="Σ waste kg × cost per kg" empty={empty}>
                <ResponsiveContainer><LineChart data={s} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
                  <CartesianGrid {...gridProps} /><XAxis dataKey="label" {...axisProps} minTickGap={24} /><YAxis {...yAxisProps} width={62} tickFormatter={v => '₹' + fmt(v / 1000) + 'k'} />
                  <Tooltip cursor={cursor} content={<Tip format={v => inr(v)} />} />{line('waste_cost', 'Waste cost', C.s3)}
                </LineChart></ResponsiveContainer>
              </ChartCard>
              <ChartCard title="9. Potential savings trend" subtitle="Estimated monthly saving vs the baseline (not verified)" empty={!data.savings.length}>
                <ResponsiveContainer><BarChart data={data.savings} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
                  <CartesianGrid {...gridProps} /><XAxis dataKey="label" {...axisProps} /><YAxis {...yAxisProps} width={62} tickFormatter={v => '₹' + fmt(v / 1000) + 'k'} />
                  <Tooltip cursor={barCursor} content={<Tip format={v => inr(v)} />} />{bar('estimated_saving', 'Estimated saving', C.s1)}
                </BarChart></ResponsiveContainer>
              </ChartCard>
              <Card title="10. Slot booking utilisation" subtitle="Average bookings as a share of capacity">
                {!data.slot_history.length ? <Empty title="No booking data in this range">Bookings appear once students use slot booking.</Empty> : (
                  <div className="stack" style={{ gap: 18, paddingTop: 6 }}>
                    {data.slot_history.map(x => (
                      <div key={x.meal_type}>
                        <div className="between small"><span className="strong">{cap(x.meal_type)}</span><span className="muted">{fmt(x.avg_bookings)} of {x.capacity} seats · <b>{pct(x.avg_utilization, 0)}</b></span></div>
                        <div className="meter mt-8" style={{ height: 10 }}><i style={{ width: `${Math.min(100, x.avg_utilization)}%`, background: MEAL_COLOR[x.meal_type] }} /></div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </div>
            {!empty && (
              <Card title="Data table" subtitle="The numbers behind the charts">
                <div className="table-wrap flush" style={{ maxHeight: 360, overflowY: 'auto' }}>
                  <table className="table compact">
                    <thead><tr><th>Period</th><th className="num">Confirmed</th><th className="num">Attendance</th><th className="num">Prepared</th><th className="num">Served</th><th className="num">Waste kg</th><th className="num">Waste %</th><th className="num">Cost</th></tr></thead>
                    <tbody>{s.map(x => <tr key={x.period}><td>{x.label}</td><td className="num">{fmt(x.conf)}</td><td className="num">{fmt(x.att)}</td><td className="num">{fmt(x.prepared)}</td><td className="num">{fmt(x.served)}</td><td className="num">{fmt(x.waste_kg, 1)}</td><td className="num">{pct(x.waste_pct)}</td><td className="num">{inr(x.waste_cost)}</td></tr>)}</tbody>
                  </table>
                </div>
              </Card>
            )}
            <ModelCard />
          </>
        )
      })()}
    </div>
  )
}
