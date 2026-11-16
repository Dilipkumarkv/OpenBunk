import { HashRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './components/AuthProvider'
import Layout from './components/Layout'
import { ToastProvider } from './components/Toast'
import Credit from './pages/Credit'
import Dashboard from './pages/Dashboard'
import Fuel from './pages/Fuel'
import Login from './pages/Login'
import Reports from './pages/Reports'
import Settings from './pages/Settings'
import Shifts from './pages/Shifts'

// HashRouter so the static build works on any file host / GitHub Pages
// without server-side SPA rewrite rules. Revisit if a server is added later.
export default function App() {
  return (
    <HashRouter>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route element={<Layout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/shifts" element={<Shifts />} />
              <Route path="/fuel" element={<Fuel />} />
              <Route path="/credit" element={<Credit />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </HashRouter>
  )
}
