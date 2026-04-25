import { Navigate, Route, Routes } from 'react-router-dom'

import { AppShellLayout } from './components/AppShellLayout'
import { ProtectedRoute } from './components/ProtectedRoute'
import { useAuth } from './context/AuthContext'
import { BehaviorLogsPage } from './pages/BehaviorLogsPage'
import { DownloadsPage } from './pages/DownloadsPage'
import { ForbiddenPage } from './pages/ForbiddenPage'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { StudentDashboardPage } from './pages/StudentDashboardPage'
import { StudentsPage } from './pages/StudentsPage'
import { TestsPage } from './pages/TestsPage'

function LandingRedirect() {
  const { user, isAuthenticated } = useAuth()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (user?.role === 'student') return <Navigate to="/student" replace />
  return <Navigate to="/portal/tests" replace />
}

export function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<LandingRedirect />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/forbidden" element={<ForbiddenPage />} />

      <Route element={<ProtectedRoute allowedRoles={['admin', 'teacher']} />}>
        <Route
          path="/portal/*"
          element={
            <AppShellLayout>
              <Routes>
                <Route path="tests" element={<TestsPage />} />
                <Route path="students" element={<StudentsPage />} />
                <Route path="logs" element={<BehaviorLogsPage />} />
                <Route path="downloads" element={<DownloadsPage />} />
                <Route path="*" element={<Navigate to="tests" replace />} />
              </Routes>
            </AppShellLayout>
          }
        />
      </Route>

      <Route element={<ProtectedRoute allowedRoles={['student']} />}>
        <Route
          path="/student/*"
          element={
            <AppShellLayout>
              <Routes>
                <Route index element={<StudentDashboardPage />} />
                <Route path="downloads" element={<DownloadsPage />} />
                <Route path="*" element={<Navigate to="" replace />} />
              </Routes>
            </AppShellLayout>
          }
        />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
