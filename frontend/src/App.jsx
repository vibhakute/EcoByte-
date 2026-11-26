import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { RequireRole, useAuth } from './auth'
import AdminLayout from './layouts/AdminLayout'
import StudentLayout from './layouts/StudentLayout'
import Login from './pages/Login'
import Register from './pages/Register'
import { PageLoading } from './components/ui'

const S = {
  Dashboard: lazy(() => import('./pages/student/Dashboard')),
  Attendance: lazy(() => import('./pages/student/Attendance')),
  Menu: lazy(() => import('./pages/student/Menu')),
  Booking: lazy(() => import('./pages/student/Booking')),
  Rewards: lazy(() => import('./pages/student/Rewards')),
  History: lazy(() => import('./pages/student/History')),
  Store: lazy(() => import('./pages/student/Store')),
  Profile: lazy(() => import('./pages/student/Profile')),
}
const A = {
  Overview: lazy(() => import('./pages/admin/Overview')),
  Students: lazy(() => import('./pages/admin/Students')),
  StudentProfile: lazy(() => import('./pages/admin/StudentProfile')),
  Holidays: lazy(() => import('./pages/admin/Holidays')),
  Store: lazy(() => import('./pages/admin/Store')),
  Meals: lazy(() => import('./pages/admin/MealPlanning')),
  Analytics: lazy(() => import('./pages/admin/Analytics')),
  Waste: lazy(() => import('./pages/admin/Waste')),
  Costs: lazy(() => import('./pages/admin/Costs')),
  Savings: lazy(() => import('./pages/admin/Savings')),
  Attendance: lazy(() => import('./pages/admin/Attendance')),
  Slots: lazy(() => import('./pages/admin/Slots')),
  Rewards: lazy(() => import('./pages/admin/Rewards')),
  Donations: lazy(() => import('./pages/admin/Donations')),
  Reports: lazy(() => import('./pages/admin/Reports')),
  Settings: lazy(() => import('./pages/admin/Settings')),
}
const DonationResponse = lazy(() => import('./pages/DonationResponse'))
const page = El => <Suspense fallback={<PageLoading />}><El /></Suspense>

/** The site opens straight on the sign-in page; signed-in users go to their own dashboard. */
function Home() {
  const { user } = useAuth()
  if (user) return <Navigate to={user.role === 'admin' ? '/admin' : '/student'} replace />
  return <Login portal="student" />
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login portal="student" />} />
      <Route path="/register" element={<Register />} />
      <Route path="/admin/login" element={<Login portal="admin" />} />
      {/* Public NGO response page: secret link, no login, no NGO dashboard. */}
      <Route path="/d/:token" element={page(DonationResponse)} />

      <Route path="/student" element={<RequireRole role="student"><StudentLayout /></RequireRole>}>
        <Route index element={page(S.Dashboard)} />
        <Route path="attendance" element={page(S.Attendance)} />
        <Route path="menu" element={page(S.Menu)} />
        <Route path="booking" element={page(S.Booking)} />
        <Route path="rewards" element={page(S.Rewards)} />
        <Route path="history" element={page(S.History)} />
        <Route path="store" element={page(S.Store)} />
        <Route path="profile" element={page(S.Profile)} />
      </Route>

      <Route path="/admin" element={<RequireRole role="admin"><AdminLayout /></RequireRole>}>
        <Route index element={page(A.Overview)} />
        <Route path="students" element={page(A.Students)} />
        <Route path="students/:id" element={page(A.StudentProfile)} />
        <Route path="holidays" element={page(A.Holidays)} />
        <Route path="store" element={page(A.Store)} />
        <Route path="meals" element={page(A.Meals)} />
        <Route path="analytics" element={page(A.Analytics)} />
        <Route path="waste" element={page(A.Waste)} />
        <Route path="costs" element={page(A.Costs)} />
        <Route path="savings" element={page(A.Savings)} />
        <Route path="attendance" element={page(A.Attendance)} />
        <Route path="slots" element={page(A.Slots)} />
        <Route path="rewards" element={page(A.Rewards)} />
        <Route path="donations" element={page(A.Donations)} />
        <Route path="reports" element={page(A.Reports)} />
        <Route path="settings" element={page(A.Settings)} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
