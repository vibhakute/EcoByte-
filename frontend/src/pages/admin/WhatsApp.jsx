import { useEffect, useState } from 'react'
import { CheckCircle2, CircleAlert, MessageCircle, RefreshCw, Save, Send } from 'lucide-react'
import { api, useApi } from '../../api'
import { Alert, Badge, Card, Empty, Field, Loading, Seg, prettyTime, useAction } from '../../components/ui'

export const WA_STATUS = {
  pending: ['Sending…', 'amber'], sent: ['Sent', 'blue'], delivered: ['Delivered', 'green'], read: ['Read', 'solid'],
  failed: ['Failed', 'red'], received: ['Reply received', 'purple'],
}
export const WaBadge = ({ s }) => <Badge tone={WA_STATUS[s]?.[1]}>{WA_STATUS[s]?.[0] || s}</Badge>
const FINAL = ['delivered', 'read', 'failed', 'received']

export function useWhatsApp() {
  return useApi('/admin/whatsapp/config')
}

/** Message log, polling while any message is still on its way. */
export function MessageLog({ donationId, refreshKey = 0, compact }) {
  const params = donationId ? { donation_id: donationId } : undefined
  const { data, loading, reload } = useApi('/admin/whatsapp/messages', params)
  const [run, busy] = useAction()
  useEffect(() => { reload(true) }, [refreshKey]) // eslint-disable-line react-hooks/exhaustive-deps
  const waiting = (data || []).some(m => !FINAL.includes(m.status) && m.provider === 'twilio')
  useEffect(() => {
    if (!waiting) return
    const t = setInterval(() => reload(true), 6000)
    return () => clearInterval(t)
  }, [waiting, reload])
  if (loading && !data) return <Loading />
  if (!data?.length) return <Empty icon={MessageCircle} title="No WhatsApp messages yet">Send a test message to check your setup.</Empty>
  return (
    <div className="table-wrap flush">
      <table className="table compact">
        <thead><tr><th>Time</th><th>To / from</th>{!compact && <th>Type</th>}<th>Status</th><th>Details</th><th /></tr></thead>
        <tbody>{data.map(m => (
          <tr key={m.id}>
            <td className="small muted nowrap">{prettyTime(m.created_at)}</td>
            <td className="small"><b>{m.ngo_name || (m.direction === 'in' ? 'Incoming' : 'Number')}</b><div className="tiny faint">+{m.phone}</div></td>
            {!compact && <td className="small">{m.direction === 'in' ? 'Reply' : m.kind === 'test' ? 'Test' : 'Donation'} · {m.provider === 'meta' ? 'Meta' : 'Twilio'}</td>}
            <td><WaBadge s={m.status} /></td>
            <td className="small" style={{ maxWidth: 420 }}>
              {m.error ? <span style={{ color: 'var(--crit-text)' }}>{m.error}</span>
                : <span className="muted">{m.direction === 'in' ? m.body : m.status === 'sent' && m.provider === 'meta'
                  ? 'Accepted by WhatsApp. Delivered/read appears here once the webhook is connected; otherwise check the phone.'
                  : m.body.split('\n')[0].slice(0, 90)}</span>}
            </td>
            <td className="right">{m.provider === 'twilio' && !FINAL.includes(m.status) &&
              <button className="btn sm ghost icon-btn" aria-label="Refresh status" disabled={busy} onClick={() => run(() => api(`/admin/whatsapp/messages/${m.id}/refresh`, { method: 'POST' })).then(() => reload(true))}><RefreshCw size={14} /></button>}</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  )
}

export function WhatsAppSetup({ onChange }) {
  const { data, error, loading, reload } = useWhatsApp()
  const settings = useApi('/admin/settings')
  const [f, setF] = useState(null)
  const [test, setTest] = useState({ phone: '', mode: 'text' })
  const [last, setLast] = useState(null)
  const [logKey, setLogKey] = useState(0)
  const [run, busy] = useAction()
  useEffect(() => { if (data) setF({ ...data, meta_token: '', meta_app_secret: '', twilio_token: '' }) }, [data])
  if (loading && !data) return <Loading />
  if (error) return <Alert tone="error">{error}</Alert>
  if (!f) return null
  const set = k => e => setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  const base = settings.data?.public_base_url || window.location.origin
  const localLinks = /localhost|127\.0\.0\.1/.test(base)

  async function save() {
    const body = {
      provider: f.provider, auto_send: f.auto_send, meta_phone_number_id: f.meta_phone_number_id.trim(), meta_token: f.meta_token || null,
      meta_app_secret: f.meta_app_secret || null, meta_verify_token: f.meta_verify_token.trim(), meta_template: f.meta_template.trim(),
      meta_template_lang: f.meta_template_lang.trim() || 'en_US', twilio_sid: f.twilio_sid.trim(), twilio_token: f.twilio_token || null,
      twilio_from: f.twilio_from.trim(),
    }
    if (await run(() => api('/admin/whatsapp/config', { method: 'PUT', body }), 'WhatsApp settings saved')) { reload(true); onChange?.() }
  }
  async function sendTest() {
    const r = await run(() => api('/admin/whatsapp/test', { method: 'POST', body: test }))
    if (r) { setLast(r); setLogKey(k => k + 1) }
  }
  const secret = (k, label, hint) => (
    <Field label={label} hint={data[k].set ? `Saved (${data[k].hint}). Leave blank to keep it.` : hint}>
      <input className="input" type="password" autoComplete="off" value={f[k]} onChange={set(k)} placeholder={data[k].set ? '••••••••  (saved)' : ''} />
    </Field>
  )

  return (
    <div className="stack">
      {data.ready
        ? <Alert tone="success" title="Automatic WhatsApp is ready.">Messages are sent through {data.provider === 'meta' ? 'the Meta WhatsApp Cloud API' : 'Twilio'}. {data.auto_send ? 'New donations are sent to every active NGO automatically.' : 'Use “Send automatically” on a donation, or turn on auto-send below.'}</Alert>
        : <Alert tone="info" title="Automatic WhatsApp is not set up.">{data.problem} Until then, “Send to NGOs via WhatsApp” opens a pre-filled chat that you send yourself.</Alert>}
      {localLinks && <Alert tone="warn" title="NGO links point to this computer.">The accept/decline links in messages use <b>{base}</b>, which NGO phones cannot open. Set a public address in Settings → Public web address (for testing, run a tunnel such as <code>cloudflared tunnel --url http://localhost:8000</code> and paste its https address).</Alert>}

      <div className="grid g-2" style={{ alignItems: 'start' }}>
        <Card title="1. Connect a WhatsApp provider">
          <div className="stack">
            <Seg value={f.provider} onChange={v => setF({ ...f, provider: v })} options={[{ value: 'off', label: 'Off' }, { value: 'twilio', label: 'Twilio sandbox' }, { value: 'meta', label: 'Meta Cloud API' }]} />
            {f.provider === 'twilio' && <>
              <ol className="small muted" style={{ margin: 0, paddingLeft: 18, lineHeight: 1.6 }}>
                <li>Create a free account at twilio.com → Messaging → Try it out → <b>Send a WhatsApp message</b>.</li>
                <li>From each test phone, send <b>join &lt;your-sandbox-word&gt;</b> to <b>+1 415 523 8886</b> on WhatsApp.</li>
                <li>Copy the Account SID and Auth Token from the Twilio console below.</li>
              </ol>
              <div className="form-grid">
                <Field label="Account SID" className="span-all"><input className="input" value={f.twilio_sid} onChange={set('twilio_sid')} placeholder="AC…" /></Field>
                {secret('twilio_token', 'Auth Token', 'From the Twilio console')}
                <Field label="WhatsApp From number" hint="Sandbox: 14155238886"><input className="input" value={f.twilio_from} onChange={set('twilio_from')} placeholder="14155238886" /></Field>
              </div>
            </>}
            {f.provider === 'meta' && <>
              <ol className="small muted" style={{ margin: 0, paddingLeft: 18, lineHeight: 1.6 }}>
                <li>At developers.facebook.com create an app → add <b>WhatsApp</b> → <b>API Setup</b>.</li>
                <li>Under “To”, add and verify each test number (up to 5 on the free test number).</li>
                <li>Copy the <b>Phone number ID</b> and the <b>access token</b> below.</li>
                <li>Plain text only arrives if the NGO messaged your number in the last 24 h. For first contact, send the <b>hello_world</b> test, or create a template (below).</li>
              </ol>
              <div className="form-grid">
                <Field label="Phone number ID"><input className="input" value={f.meta_phone_number_id} onChange={set('meta_phone_number_id')} placeholder="e.g. 1234567890" /></Field>
                {secret('meta_token', 'Access token', 'Temporary tokens expire after 24 h')}
                <Field label="Donation template (optional)" hint="Approved template with 6 variables; blank = plain text"><input className="input" value={f.meta_template} onChange={set('meta_template')} placeholder="e.g. food_donation_alert" /></Field>
                <Field label="Template language"><input className="input" value={f.meta_template_lang} onChange={set('meta_template_lang')} /></Field>
              </div>
              <details className="small"><summary className="strong" style={{ cursor: 'pointer' }}>Delivery receipts (webhook) and template text</summary>
                <div className="stack mt-8" style={{ gap: 10 }}>
                  <p className="muted">In Meta → WhatsApp → Configuration, set the callback URL to <code>{data.webhook_url}</code> (must be public HTTPS), use the verify token below, and subscribe to <b>messages</b>. Then Delivered / Read / Failed and NGO replies appear in the log.</p>
                  <div className="form-grid">
                    <Field label="Verify token" hint="Any secret word; type the same in Meta"><input className="input" value={f.meta_verify_token} onChange={set('meta_verify_token')} /></Field>
                    {secret('meta_app_secret', 'App secret', 'App settings → Basic; used to check webhook signatures')}
                  </div>
                  <p className="muted">Suggested template body (category Utility):</p>
                  <pre className="formula" style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', margin: 0 }}>{'Surplus food from {{1}}: {{2}}, {{3}} available. Pickup at {{4}} by {{5}}. Accept or decline here: {{6}}'}</pre>
                </div>
              </details>
            </>}
            {f.provider !== 'off' && <label className="check"><input type="checkbox" checked={f.auto_send} onChange={set('auto_send')} />
              <span><b>Auto-send new donations</b> to every active NGO as soon as a donation is created</span></label>}
            <div className="row"><button className="btn primary" disabled={busy} onClick={save}><Save />Save</button></div>
          </div>
        </Card>

        <Card title="2. Send a test message">
          <div className="stack">
            <p className="small muted">Send a real WhatsApp message to your own phone (or an NGO's) to check that delivery works.</p>
            <div className="form-grid">
              <Field label="WhatsApp number" hint="With country code" className={data.provider === 'meta' ? '' : 'span-all'}>
                <input className="input" value={test.phone} onChange={e => setTest({ ...test, phone: e.target.value })} placeholder="+91 98765 43210" /></Field>
              {data.provider === 'meta' && <Field label="Message type"><select className="select" value={test.mode} onChange={e => setTest({ ...test, mode: e.target.value })}>
                <option value="text">Plain text (24-hour window)</option><option value="hello_world">hello_world template (always allowed)</option></select></Field>}
            </div>
            <div className="row"><button className="btn whatsapp" disabled={busy || !data.ready || test.phone.replace(/\D/g, '').length < 10} onClick={sendTest}><Send />{busy ? 'Sending…' : 'Send test message'}</button>
              {!data.ready && <span className="small muted">Save a provider first.</span>}</div>
            {last && (last.status === 'failed'
              ? <Alert tone="error" title="Not sent.">{last.error}</Alert>
              : <Alert tone="success" title={last.provider === 'meta' ? 'Accepted by WhatsApp.' : 'Sent to Twilio.'}>Check the phone. The status below updates as WhatsApp reports delivery{last.provider === 'meta' ? ' (needs the webhook)' : ''}.</Alert>)}
          </div>
        </Card>
      </div>

      <Card viewAll title="Message log" subtitle="Every automatic WhatsApp message and its delivery status"
        actions={<button className="btn sm ghost" onClick={() => setLogKey(k => k + 1)}><RefreshCw size={14} />Refresh</button>}>
        <MessageLog refreshKey={logKey} />
      </Card>
    </div>
  )
}

export function SendResults({ results }) {
  return (
    <div className="list">{results.map(r => (
      <div className="list-item" key={r.id}>
        <div className="row" style={{ gap: 10 }}>{r.status === 'failed' ? <CircleAlert size={18} color="var(--crit-text)" /> : <CheckCircle2 size={18} color="var(--brand)" />}
          <div><div className="small strong">{r.ngo_name}</div><div className="tiny faint">+{r.phone}</div>
            {r.error && <div className="tiny" style={{ color: 'var(--crit-text)', maxWidth: 420 }}>{r.error}</div>}</div></div>
        <WaBadge s={r.status} />
      </div>
    ))}</div>
  )
}
