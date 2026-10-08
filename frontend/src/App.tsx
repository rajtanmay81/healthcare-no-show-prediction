import { lazy, Suspense, type ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Spinner } from './components/ui'
import { AuthProvider, useAuth } from './hooks/useAuth'
const AnalyticsPage = lazy(() => import('./pages/Analytics'))
const AppointmentDetailPage = lazy(() => import('./pages/AppointmentDetail'))
const AppointmentsPage = lazy(() => import('./pages/Appointments'))
const AssistantPage = lazy(() => import('./pages/Assistant'))
const DashboardPage = lazy(() => import('./pages/Dashboard'))
const DepartmentsPage = lazy(() => import('./pages/Departments'))
const DoctorsPage = lazy(() => import('./pages/Doctors'))
const LoginPage = lazy(() => import('./pages/Login'))
const PatientsPage = lazy(() => import('./pages/Patients'))
const PredictionsPage = lazy(() => import('./pages/Predictions'))

function Protected({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <Spinner label="Checking session…" />
  return user ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Suspense fallback={<Spinner />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<Protected><Layout /></Protected>}>
            <Route index element={<DashboardPage />} />
            <Route path="appointments" element={<AppointmentsPage />} />
            <Route path="appointments/:id" element={<AppointmentDetailPage />} />
            <Route path="patients" element={<PatientsPage />} />
            <Route path="doctors" element={<DoctorsPage />} />
            <Route path="departments" element={<DepartmentsPage />} />
            <Route path="predictions" element={<PredictionsPage />} />
            <Route path="analytics" element={<AnalyticsPage />} />
            <Route path="assistant" element={<AssistantPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </Suspense>
      </BrowserRouter>
    </AuthProvider>
  )
}
