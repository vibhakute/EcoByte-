import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import Logo from '../components/Logo'
import { Alert, Field, Spinner } from '../components/ui'

export default function Register() {
  const { register } = useAuth()
  const nav = useNavigate()
  const [f, setF] = useState({ name: '', email: '', student_code: '', department: '', year_of_study: '', password: '' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = k => e => setF({ ...f, [k]: e.target.value })

  async function submit(e) {
    e.preventDefault()
    if (f.password.length < 8) return setError('Password must be at least 8 characters.')
    setBusy(true); setError(null)
    try {
      await register({ ...f, year_of_study: f.year_of_study ? Number(f.year_of_study) : null, department: f.department || null })
      nav('/student', { replace: true })
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <div className="auth-main" style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      <form className="card card-pad stack" style={{ width: '100%', maxWidth: 480 }} onSubmit={submit}>
        <Link to="/"><Logo /></Link>
        <div><h1>Create your student account</h1><p className="muted mt-4">Use your college email and student ID.</p></div>
        {error && <Alert tone="error">{error}</Alert>}
        <div className="form-grid">
          <Field label="Full name" className="span-2"><input className="input" value={f.name} onChange={set('name')} required /></Field>
          <Field label="College email" className="span-2"><input className="input" type="email" value={f.email} onChange={set('email')} required /></Field>
          <Field label="Student ID"><input className="input" value={f.student_code} onChange={set('student_code')} required /></Field>
          <Field label="Year">
            <select className="select" value={f.year_of_study} onChange={set('year_of_study')}>
              <option value="">Select</option>{[1, 2, 3, 4].map(y => <option key={y} value={y}>Year {y}</option>)}
            </select>
          </Field>
          <Field label="Department" className="span-2"><input className="input" value={f.department} onChange={set('department')} /></Field>
          <Field label="Password" hint="At least 8 characters" className="span-2"><input className="input" type="password" autoComplete="new-password" value={f.password} onChange={set('password')} required /></Field>
        </div>
        <button className="btn primary lg block" disabled={busy}>{busy ? <Spinner /> : 'Create account'}</button>
        <div className="small muted">Already registered? <Link className="strong" style={{ color: 'var(--brand)' }} to="/login">Sign in</Link></div>
      </form>
    </div>
  )
}
