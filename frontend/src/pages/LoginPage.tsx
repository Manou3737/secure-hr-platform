import { useRef, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import ErrorMessage from '../components/ui/ErrorMessage'

export default function LoginPage() {
  const { login, isLoading } = useAuth()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const submissionInProgress = useRef(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (submissionInProgress.current || isLoading) {
      return
    }

    submissionInProgress.current = true
    setError('')

    try {
      await login(email.trim(), password)
      navigate('/dashboard', { replace: true })
    } catch {
      setError(
        'Unable to sign in. Check your credentials and account verification.',
      )
    } finally {
      submissionInProgress.current = false
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
      <section className="w-full max-w-md rounded-xl bg-white p-8 shadow">
        <h1 className="text-2xl font-bold text-slate-900">
          Secure HR Platform
        </h1>

        <p className="mt-2 text-sm text-slate-600">
          Sign in to your account
        </p>

        <form onSubmit={handleSubmit} className="mt-8 space-y-5">
          <Input
            label="Email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />

          <Input
            label="Password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />

          <ErrorMessage message={error} />

          <Button
            type="submit"
            disabled={isLoading}
            className="w-full"
          >
            {isLoading ? 'Signing in...' : 'Sign in'}
          </Button>
        </form>
      </section>
    </main>
  )
}
