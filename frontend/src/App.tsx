import { AuthProvider } from './auth/AuthContext'
import AppRouter from './app/router'

import { ToastProvider } from './components/ui/ToastProvider'
function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <AppRouter />
      </ToastProvider>
    </AuthProvider>
  )
}

export default App
