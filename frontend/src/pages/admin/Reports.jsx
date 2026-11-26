import { useRef, useState } from 'react'
import { CalendarCheck, Download, FileSpreadsheet, HandHeart, Trash2, Upload } from 'lucide-react'
import { api, download, useApi } from '../../api'
import { Alert, Badge, Card, Empty, Field, Loading, PageHeader, addDays, fmt, prettyTime, todayIso, useAction } from '../../components/ui'

function ExportCard({ icon: Icon, title, text, path, file, withRange = true, defaultDays = 30, future = 0 }) {
  const [r, setR] = useState({ start: addDays(todayIso(), -defaultDays), end: addDays(todayIso(), future) })
  const [run, busy] = useAction()
  return (
    <Card title={<><Icon />{title}</>} subtitle={text}>
      <div className="row wrap" style={{ gap: 10, alignItems: 'flex-end' }}>
        {withRange && <>
          <Field label="From"><input type="date" className="input sm" value={r.start} onChange={e => setR({ ...r, start: e.target.value })} /></Field>
          <Field label="To"><input type="date" className="input sm" value={r.end} onChange={e => setR({ ...r, end: e.target.value })} /></Field>
        </>}
        <button className="btn primary sm" disabled={busy} onClick={() => run(() => download(path, withRange ? r : {}, file(r)), `${title} downloaded`)}><Download />Download .xlsx</button>
      </div>
    </Card>
  )
}

export default function Reports() {
  const logs = useApi('/admin/imports')
  const status = useApi('/admin/data-status')
  const [file, setFile] = useState(null)
  const [synthetic, setSynthetic] = useState(false)
  const [result, setResult] = useState(null)
  const [run, busy] = useAction()
  const input = useRef()
  async function upload() {
    const fd = new FormData()
    fd.append('file', file)
    const r = await run(() => api('/admin/import', { method: 'POST', body: fd, params: { synthetic } }), x => `Imported ${x.rows_imported} rows`)
    if (r) { setResult(r); setFile(null); if (input.current) input.current.value = ''; logs.reload(true); status.reload(true) }
  }
  return (
    <div className="stack">
      <PageHeader title="Reports" subtitle="Download Excel reports and import historical canteen records." />
      <div className="grid g-2">
        <ExportCard icon={FileSpreadsheet} title="Full operations report" text="Daily records, weekly/monthly/annual summaries and the savings ledger" path="/admin/reports/export" defaultDays={365} file={r => `EcoByte_Report_${r.start}_${r.end}.xlsx`} />
        <ExportCard icon={CalendarCheck} title="Attendance report" text="Every student's breakfast / lunch / dinner confirmation with timestamps and arrivals" path="/admin/reports/attendance" future={14} file={r => `EcoByte_Attendance_${r.start}_${r.end}.xlsx`} />
        <ExportCard icon={Trash2} title="Waste report" text="Every waste entry with food, weights, rate and cost" path="/admin/reports/waste" defaultDays={90} file={r => `EcoByte_Waste_${r.start}_${r.end}.xlsx`} />
        <ExportCard icon={HandHeart} title="Donation history" text="All donations with NGO allocations, quantities and statuses" path="/admin/reports/donations" withRange={false} file={() => 'EcoByte_Donations.xlsx'} />
      </div>

      <Card viewAll title={<><Upload />Import historical data</>} subtitle="Excel (.xlsx). Columns are matched by name, ignoring case and spacing. Required: Date, Actual_Attendance, Meals_Prepared.">
        <div className="stack">
          {status.data?.has_synthetic && <Alert tone="warn">The current history includes <b>synthetic</b> demonstration data ({fmt(status.data.synthetic_records)} service records). Importing real records for the same dates and meals replaces them.</Alert>}
          <div className="row wrap" style={{ gap: 12 }}>
            <input ref={input} className="input" type="file" accept=".xlsx,.xls" style={{ maxWidth: 360, paddingTop: 6 }} onChange={e => setFile(e.target.files[0] || null)} />
            <label className="check"><input type="checkbox" checked={synthetic} onChange={e => setSynthetic(e.target.checked)} />This file is synthetic / demonstration data</label>
            <button className="btn primary" disabled={!file || busy} onClick={upload}><Upload />{busy ? 'Importing…' : 'Validate & import'}</button>
          </div>
          {result && <>
            <Alert tone={result.rows_skipped ? 'warn' : 'success'}>Sheet <b>{result.sheet}</b>: {result.rows_imported} imported, {result.rows_skipped} skipped of {result.rows_read} rows.</Alert>
            {result.messages.length > 0 && <ul className="small muted" style={{ margin: 0, paddingLeft: 18, maxHeight: 160, overflowY: 'auto' }}>{result.messages.map((m, i) => <li key={i}>{m}</li>)}</ul>}
          </>}
          <div className="small strong mt-8">Import history</div>
          {logs.loading && !logs.data ? <Loading /> : !logs.data?.length ? <Empty title="No imports yet" /> : (
            <table className="table compact">
              <thead><tr><th>File</th><th>When</th><th className="num">Imported</th><th className="num">Skipped</th><th>Data</th></tr></thead>
              <tbody>{logs.data.map(l => <tr key={l.id}><td className="small strong">{l.filename}</td><td className="small muted">{prettyTime(l.imported_at)}</td><td className="num">{fmt(l.rows_imported)}</td><td className="num">{fmt(l.rows_skipped)}</td><td>{l.is_synthetic ? <Badge tone="amber">Synthetic</Badge> : <Badge tone="green">Real</Badge>}</td></tr>)}</tbody>
            </table>
          )}
        </div>
      </Card>
    </div>
  )
}
