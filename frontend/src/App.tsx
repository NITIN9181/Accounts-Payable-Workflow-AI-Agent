import { QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { queryClient } from './lib/queryClient'
import { AuthProvider, useAuth } from './context/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import ExceptionDetailPage from './pages/ExceptionDetailPage'
import InvoiceDetailPage from './pages/InvoiceDetailPage'
import VendorAnalyticsPage from './pages/VendorAnalyticsPage'
import PaymentSchedulePage from './pages/PaymentSchedulePage'
import SettingsPage from './pages/SettingsPage'

/**
 * Inner App component that uses auth context
 */
function AppContent() {
  const { isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-600 to-blue-800 flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-white border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-white text-lg">Loading...</p>
        </div>
      </div>
    )
  }

  return (
    <Router>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <Routes>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/exceptions/:id" element={<ExceptionDetailPage />} />
                <Route path="/invoices/:id" element={<InvoiceDetailPage />} />
                <Route path="/vendors/:vendorKey" element={<VendorAnalyticsPage />} />
                <Route path="/payments" element={<PaymentSchedulePage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/profile" element={<div>Profile (TODO)</div>} />
                <Route path="/search" element={<div>Search Results (TODO)</div>} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </ProtectedRoute>
          }
        />
      </Routes>
    </Router>
  )
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </QueryClientProvider>
  )
}

export default App
