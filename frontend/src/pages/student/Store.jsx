import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, Minus, Plus, ShoppingBag, ShoppingCart, X } from 'lucide-react'
import { api, useApi } from '../../api'
import { ProductImage } from '../../components/Illustrations'
import { Alert, Badge, Card, Empty, ErrorState, Field, Loading, Modal, PageHeader, Seg, Tabs, cap, inr, prettyTime, useAction, ViewAll } from '../../components/ui'

const TONE = { placed: 'amber', accepted: 'blue', preparing: 'purple', ready: 'green', completed: 'solid', cancelled: '' }
const STEPS = ['placed', 'accepted', 'preparing', 'ready', 'completed']
const CART_KEY = 'ecobyte_cart'
const loadCart = () => { try { return JSON.parse(sessionStorage.getItem(CART_KEY) || '{}') } catch { return {} } }

function Qty({ value, onChange, max = 20 }) {
  return (
    <span className="qty">
      <button type="button" aria-label="Decrease" onClick={() => onChange(value - 1)}><Minus size={14} /></button>
      <span>{value}</span>
      <button type="button" aria-label="Increase" disabled={value >= max} onClick={() => onChange(value + 1)}><Plus size={14} /></button>
    </span>
  )
}

function OrderTracker({ o }) {
  if (o.status === 'cancelled') return <Badge>Cancelled</Badge>
  const i = STEPS.indexOf(o.status)
  return (
    <div className="row wrap" style={{ gap: 4 }}>
      {STEPS.map((s, k) => <span key={s} className={`badge ${k <= i ? 'green' : ''}`} style={{ opacity: k <= i ? 1 : .55 }}>{k <= i && <CheckCircle2 size={12} />}{s === 'ready' ? 'Ready for pickup' : cap(s)}</span>)}
    </div>
  )
}

function Orders({ reloadKey }) {
  const { data, error, loading, reload } = useApi('/student/store/orders', null, [reloadKey])
  const [run, busy] = useAction()
  useEffect(() => { const t = setInterval(() => reload(true), 15000); return () => clearInterval(t) }, [reload])
  if (loading && !data) return <Loading rows={4} />
  if (error) return <ErrorState error={error} onRetry={reload} />
  if (!data.length) return <Card><Empty icon={ShoppingBag} title="No orders yet">Your canteen store orders will appear here.</Empty></Card>
  return (
    <ViewAll limit={4} noun="orders"><div className="stack" data-viewall>{data.map(o => (
      <div key={o.id} className="card card-pad stack" style={{ gap: 10 }}>
        <div className="between wrap"><div><b>{o.code}</b><span className="tiny faint"> · {prettyTime(o.created_at)}</span></div><Badge tone={TONE[o.status]}>{o.status_label}</Badge></div>
        <OrderTracker o={o} />
        <div className="small">{o.items.map(i => `${i.quantity} × ${i.name}`).join(' · ')}</div>
        <div className="between"><span className="small muted">{o.status === 'ready' ? 'Collect at the counter and pay there.' : o.note ? `Note: ${o.note}` : 'Pay at the counter on pickup.'}</span><b>{inr(o.total)}</b></div>
        {o.status === 'placed' && <div><button className="btn sm danger" disabled={busy} onClick={async () => {
          if (window.confirm(`Cancel order ${o.code}?`) && await run(() => api(`/student/store/orders/${o.id}/cancel`, { method: 'POST' }), 'Order cancelled')) reload(true)
        }}><X />Cancel order</button></div>}
      </div>
    ))}</div></ViewAll>
  )
}

export default function StudentStore() {
  const { data, error, loading, reload } = useApi('/student/store/products')
  const [tab, setTab] = useState('shop')
  const [cat, setCat] = useState('all')
  const [cart, setCart] = useState(loadCart)
  const [review, setReview] = useState(false)
  const [note, setNote] = useState('')
  const [placed, setPlaced] = useState(null)
  const [run, busy] = useAction()
  useEffect(() => { try { sessionStorage.setItem(CART_KEY, JSON.stringify(cart)) } catch { /* ignore */ } }, [cart])

  const byId = useMemo(() => Object.fromEntries((data || []).map(p => [p.id, p])), [data])
  const lines = Object.entries(cart).map(([id, q]) => ({ p: byId[id], q })).filter(l => l.p)
  const count = lines.reduce((a, l) => a + l.q, 0)
  const total = lines.reduce((a, l) => a + l.q * l.p.price, 0)
  const setQty = (id, q) => setCart(c => { const n = { ...c }; if (q <= 0) delete n[id]; else n[id] = Math.min(20, q); return n })
  const unavailable = lines.filter(l => !l.p.available)

  async function order() {
    const r = await run(() => api('/student/store/orders', { method: 'POST', body: { items: lines.map(l => ({ product_id: l.p.id, quantity: l.q })), note } }))
    if (r) { setPlaced(r); setCart({}); setNote(''); setReview(false); reload(true) }
  }

  const products = (data || []).filter(p => cat === 'all' || p.category === cat)
  return (
    <div className="stack">
      <PageHeader title="Canteen Store" subtitle="Extra snacks and drinks, separate from your mess pass. Pay at the counter when you collect." />
      {placed && <Alert tone="success" title={`Order ${placed.code} placed!`}>Total {inr(placed.total)}. We'll notify you when it's ready for pickup. Track it under “My orders”.</Alert>}
      <Tabs value={tab} onChange={setTab} options={[{ value: 'shop', label: 'Shop' }, { value: 'orders', label: 'My orders' }]} />
      {tab === 'orders' ? <Orders reloadKey={placed?.id} /> : <>
        <Seg value={cat} onChange={setCat} options={[{ value: 'all', label: 'All' }, { value: 'beverage', label: 'Beverages' }, { value: 'snack', label: 'Snacks' }, { value: 'meal', label: 'Meals' }, { value: 'dessert', label: 'Desserts' }]} />
        {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Loading rows={6} /> : !products.length ? <Card><Empty icon={ShoppingBag} title="Nothing in this category" /></Card> : (
          <div className="grid g-4">{products.map(p => (
            <div key={p.id} className="card" style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column', opacity: p.available ? 1 : .6 }}>
              <ProductImage src={p.image} category={p.category} name={p.name} />
              <div className="card-pad stack" style={{ gap: 6, padding: 14, flex: 1 }}>
                <div className="between"><span className="row"><span className={`veg ${p.is_veg ? '' : 'non'}`} /><b>{p.name}</b></span><b>{inr(p.price)}</b></div>
                <div className="small muted" style={{ flex: 1 }}>{p.description}</div>
                {!p.available ? <Badge tone="red">Unavailable</Badge>
                  : cart[p.id] ? <Qty value={cart[p.id]} onChange={q => setQty(p.id, q)} />
                    : <button className="btn sm primary" onClick={() => setQty(p.id, 1)}><Plus />Add to cart</button>}
              </div>
            </div>
          ))}</div>
        )}
        {count > 0 && (
          <div className="card card-pad between cart-bar" style={{ boxShadow: 'var(--shadow-lg)' }}>
            <span className="row"><ShoppingCart className="green" /><b>{count} item{count > 1 ? 's' : ''}</b><span className="muted">· {inr(total)}</span></span>
            <div className="row"><button className="btn ghost" onClick={() => setCart({})}>Clear</button><button className="btn primary" onClick={() => setReview(true)}>Review order</button></div>
          </div>
        )}
      </>}
      <Modal open={review} title="Your order" onClose={() => setReview(false)}
        footer={<><button className="btn ghost" onClick={() => setReview(false)}>Keep shopping</button><button className="btn primary" disabled={busy || !lines.length || unavailable.length > 0} onClick={order}>{busy ? 'Placing…' : `Place order · ${inr(total)}`}</button></>}>
        <div className="stack">
          {unavailable.length > 0 && <Alert tone="warn">{unavailable.map(l => l.p.name).join(', ')} {unavailable.length > 1 ? 'are' : 'is'} no longer available. Remove {unavailable.length > 1 ? 'them' : 'it'} to continue.</Alert>}
          {lines.map(l => (
            <div key={l.p.id} className="between"><span className="row"><b>{l.p.name}</b><span className="small muted">{inr(l.p.price)} each</span></span>
              <span className="row"><Qty value={l.q} onChange={q => setQty(l.p.id, q)} /><b style={{ width: 60, textAlign: 'right' }}>{inr(l.q * l.p.price)}</b></span></div>
          ))}
          <div className="between" style={{ borderTop: '1px solid var(--border)', paddingTop: 10 }}><b>Total</b><b style={{ fontSize: 18 }}>{inr(total)}</b></div>
          <Field label="Note for the canteen (optional)"><input className="input" value={note} onChange={e => setNote(e.target.value)} placeholder="e.g. Less sugar in tea" maxLength={300} /></Field>
          <p className="tiny faint">Prices are confirmed by the canteen when you order. Payment is made at the counter on pickup; this does not use your mess pass.</p>
        </div>
      </Modal>
    </div>
  )
}
