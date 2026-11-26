import { useState } from 'react'
import { Clock, UtensilsCrossed } from 'lucide-react'
import { useApi } from '../../api'
import { MealImage } from '../../components/Illustrations'
import { Badge, Card, Empty, ErrorState, Loading, PageHeader, addDays, cap, prettyDate, todayIso } from '../../components/ui'
import { MEAL_ICON } from '../admin/Overview'

function MealCard({ m, hours }) {
  return (
    <div className="card" style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <MealImage src={m.image} meal={m.meal_type} alt={m.name} />
      <div className="card-pad stack" style={{ gap: 8, flex: 1 }}>
        <div className="between" style={{ alignItems: 'flex-start' }}>
          <div className="row" style={{ alignItems: 'flex-start' }}><span className={`veg ${m.is_veg ? '' : 'non'}`} style={{ marginTop: 4 }} /><h2 className={m.available ? '' : 'strike'}>{m.name}</h2></div>
          {m.available ? <Badge tone="green">Available</Badge> : <Badge tone="red">Sold out</Badge>}
        </div>
        {m.description && <p className="small muted">{m.description}</p>}
        {m.items.length > 0 && <div className="row wrap" style={{ gap: 6 }}>{m.items.map(i => <Badge key={i} tone="outline">{i}</Badge>)}</div>}
        <div style={{ flex: 1 }} />
        <div className="between small"><span className="row muted"><Clock size={14} />{hours || '—'}</span><b style={{ fontSize: 16 }}>{m.price ? `₹${m.price}` : 'Included'}</b></div>
      </div>
    </div>
  )
}

export default function StudentMenu() {
  const t = todayIso()
  const days = Array.from({ length: 7 }, (_, i) => addDays(t, i))
  const [date, setDate] = useState(t)
  const { data, error, loading, reload } = useApi('/student/menu', { date })
  return (
    <div className="stack">
      <PageHeader title="Menu" subtitle="Breakfast, lunch and dinner as published by the canteen." />
      <div className="row" style={{ overflowX: 'auto', paddingBottom: 2 }}>
        {days.map((d, i) => <button key={d} className={`btn sm ${d === date ? 'primary' : ''}`} onClick={() => setDate(d)}>{i === 0 ? 'Today' : i === 1 ? 'Tomorrow' : prettyDate(d, { weekday: 'short', day: 'numeric' })}</button>)}
      </div>
      {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Loading rows={6} /> : data.closed ? (
        <Card><Empty icon={UtensilsCrossed} title="Canteen closed">{data.closed_reason}</Empty></Card>
      ) : ['breakfast', 'lunch', 'dinner'].map(meal => {
        const Icon = MEAL_ICON[meal]
        const list = data.meals[meal]
        return (
          <div key={meal} className="stack" style={{ gap: 10 }}>
            <div className="row"><Icon size={20} className="green" /><h2>{cap(meal)}</h2><span className="small muted">· {data.service_hours[meal] || ''}</span></div>
            {!list.length ? <div className="card"><Empty icon={UtensilsCrossed} title={`No ${meal} published yet`} /></div> : (
              <div className="grid g-3">{list.map(m => <MealCard key={m.id} m={m} hours={data.service_hours[meal]} />)}</div>
            )}
          </div>
        )
      })}
    </div>
  )
}
