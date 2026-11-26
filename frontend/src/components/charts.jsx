/* Chart primitives. Brand greens (dark/light differ strongly in lightness, so they stay
   distinguishable for colour-blind readers); light green is <3:1 on white, so every chart ships a
   legend + tooltip and pages pair charts with tables. One y-axis per chart, always. */
import { fmt } from './ui'

export const C = {
  s1: '#15803d', // dark green  – primary series (actual / served / leftover)
  s2: '#6cc58b', // light green – secondary series (predicted / prepared / plate)
  s3: '#eb6834', // orange      – cost
  blue: '#2a78d6',
  amber: '#e9a23b',
  grid: '#e6efe8',
  axis: '#cfdcd1',
}
export const MEAL_COLOR = { breakfast: '#e9a23b', lunch: '#15803d', dinner: '#2a78d6' }

export const axisProps = {
  tickLine: false,
  axisLine: { stroke: C.axis },
  tick: { fontSize: 11.5, fill: '#7b857f' },
}
export const yAxisProps = { ...axisProps, axisLine: false, width: 48 }
export const gridProps = { stroke: C.grid, vertical: false }

export function Legend({ items }) {
  return (
    <div className="legend">
      {items.map(i => (
        <span key={i.label}><i className={i.kind || ''} style={{ background: i.color, borderColor: i.color }} />{i.label}</span>
      ))}
    </div>
  )
}

/** Tooltip: values in text ink, a colour key beside each label. */
export function Tip({ active, payload, label, format = v => fmt(v), titleFormat, extra }) {
  if (!active || !payload?.length) return null
  const row = payload[0]?.payload || {}
  return (
    <div className="tt">
      <div className="tt-title">{titleFormat ? titleFormat(label, row) : label}</div>
      {payload.filter(p => p.value !== null && p.value !== undefined).map(p => (
        <div className="tt-row" key={p.dataKey}>
          <span className="k"><i className="dot" style={{ background: p.color || p.stroke || p.fill }} />{p.name}</span>
          <b>{format(p.value, p.dataKey)}</b>
        </div>
      ))}
      {extra && extra(row)}
    </div>
  )
}

export const cursor = { stroke: '#9aa39d', strokeWidth: 1 }
export const barCursor = { fill: 'rgba(15,26,20,.04)' }
