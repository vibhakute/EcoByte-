import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { Eye, EyeOff, GraduationCap, HandHeart, Lock, LogIn, Mail, Recycle, Settings, Sprout, TrendingUp, Users, Gift } from 'lucide-react'
import { useAuth } from '../auth'
import { BrandLogo, BrandMark, CanteenScene, Waves } from '../components/Brand'
import { Leaf } from '../components/Illustrations'
import { Alert, Modal, Spinner } from '../components/ui'

const FEATURES = [
  [TrendingUp, 'Predict', 'Meal Demand'], [Recycle, 'Reduce', 'Food Waste'], [Users, 'Track', 'Attendance'],
  [Gift, 'Earn', 'Rewards'], [HandHeart, 'Donate', 'Surplus Food'],
]
const DEMO = { student: ['STU2025', 'Student@123'], admin: ['admin@ecobyte.app', 'Admin@123'] }

export default function Login({ portal: initial }) {
  const [portal, setPortal] = useState(initial)
  const { login } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const [params] = useSearchParams()
  const [ident, setIdent] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [remember, setRemember] = useState(true)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [forgot, setForgot] = useState(false)
  useEffect(() => setPortal(initial), [initial])

  function switchTo(p) {
    setPortal(p); setError(null)
    nav(p === 'admin' ? '/admin/login' : '/login', { replace: true })
  }
  async function submit(e) {
    e.preventDefault()
    if (!ident || !password) return setError('Enter your ' + (portal === 'admin' ? 'email' : 'email or student ID') + ' and password.')
    setBusy(true); setError(null)
    try {
      await login(ident, password, portal, remember)
      nav(loc.state?.from || (portal === 'admin' ? '/admin' : '/student'), { replace: true })
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <div className="login-page">
      <Waves className="login-waves" />
      <Leaf className="login-floating-leaf" color="#7cc84f" vein="#2f8a3b" />
      <div className="login-pill"><Leaf style={{ width: 18, height: 18 }} /><b>EcoByte</b><span>·</span>Smart Campus, Green Campus</div>

      <section className="login-left">
        <Link to="/" aria-label="EcoByte home"><BrandLogo size={52} /></Link>
        <h1 className="login-headline">Smart Canteen Management &amp; Food Waste Reduction System</h1>
        <p className="login-sub">Data-Driven. Sustainable. For a Greener Tomorrow. <Leaf style={{ width: 24, height: 24, verticalAlign: '-5px' }} /></p>
        <div className="login-features">
          {FEATURES.map(([I, a, b]) => <div key={a} className="login-feature"><I /><span>{a}<br />{b}</span></div>)}
        </div>
        <div className="login-scene">
          <CanteenScene className="login-scene-art" />
          <div className="login-script"><Leaf style={{ width: 34, height: 34 }} color="#9be07a" vein="#1d6b2e" /><span>Together for<br />a Sustainable Campus</span></div>
        </div>
      </section>

      <main className="login-right">
        <form className="login-card" onSubmit={submit} noValidate>
          <div className="login-card-brand"><BrandLogo size={40} /></div>
          <div className="login-tabs" role="tablist">
            <button type="button" role="tab" aria-selected={portal === 'student'} className={portal === 'student' ? 'on' : ''} onClick={() => switchTo('student')}><GraduationCap />Student Login</button>
            <button type="button" role="tab" aria-selected={portal === 'admin'} className={portal === 'admin' ? 'on' : ''} onClick={() => switchTo('admin')}><Settings />Canteen Admin Login</button>
          </div>
          {params.get('expired') && <Alert tone="warn">Your session expired. Please sign in again.</Alert>}
          {error && <Alert tone="error">{error}</Alert>}
          <label className="login-input">
            <Mail />
            <input type="text" autoComplete="username" placeholder={portal === 'admin' ? 'Admin email' : 'Email / Student ID'} value={ident}
              onChange={e => setIdent(e.target.value)} aria-label={portal === 'admin' ? 'Admin email' : 'Email or student ID'} autoFocus />
          </label>
          <label className="login-input">
            <Lock />
            <input type={show ? 'text' : 'password'} autoComplete="current-password" placeholder="Password" value={password}
              onChange={e => setPassword(e.target.value)} aria-label="Password" />
            <button type="button" className="eye" onClick={() => setShow(!show)} aria-label={show ? 'Hide password' : 'Show password'}>{show ? <EyeOff /> : <Eye />}</button>
          </label>
          <div className="between">
            <label className="check login-remember"><input type="checkbox" checked={remember} onChange={e => setRemember(e.target.checked)} />Remember me</label>
            <button type="button" className="login-link" onClick={() => setForgot(true)}>Forgot password?</button>
          </div>
          <button className="login-submit" disabled={busy}>{busy ? <Spinner /> : <><LogIn />Sign In</>}</button>
          <div className="login-or"><span>or</span></div>
          <div className="login-tagline"><Sprout />A Smart Step Towards a Greener Future</div>
          <div className="login-meta">
            {portal === 'student' && <>New student? <Link to="/register">Create an account</Link> · </>}
            <button type="button" className="login-link small" onClick={() => { setIdent(DEMO[portal][0]); setPassword(DEMO[portal][1]) }}>Use demo account</button>
          </div>
        </form>
      </main>

      <Modal open={forgot} title="Forgot your password?" onClose={() => setForgot(false)}
        footer={<button className="btn primary" onClick={() => setForgot(false)}>Got it</button>}>
        <div className="stack" style={{ gap: 12 }}>
          <div className="row" style={{ gap: 12, alignItems: 'flex-start' }}><BrandMark size={40} />
            <p className="muted">For your security, EcoByte passwords are reset by the canteen office, not by email.</p></div>
          {portal === 'student'
            ? <p><b>Students:</b> visit or call the canteen office with your student ID. The admin will issue a temporary password from <i>Student Management → Reset password</i>; change it after signing in under <i>Profile</i>.</p>
            : <p><b>Canteen admins:</b> ask the EcoByte system owner to reset your account.</p>}
        </div>
      </Modal>
    </div>
  )
}
