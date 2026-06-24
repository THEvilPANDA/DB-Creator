import { useState } from 'react'
import { api, auth } from '../api'

type Mode = 'login' | 'register'

interface Props {
  onAuthenticated: () => void
}

export default function Login({ onAuthenticated }: Props) {
  const [mode, setMode] = useState<Mode>('login')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (mode === 'login') {
        const tokens = await api.authApi.login(username, password)
        auth.setTokens(tokens.access_token, tokens.refresh_token)
        onAuthenticated()
      } else {
        await api.authApi.register(username, email, password)
        const tokens = await api.authApi.login(username, password)
        auth.setTokens(tokens.access_token, tokens.refresh_token)
        onAuthenticated()
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      minHeight: '100vh', background: 'var(--bg-primary)',
    }}>
      <div style={{
        width: 360, background: 'var(--bg-secondary)', borderRadius: 8,
        border: '1px solid var(--border)', padding: '2rem',
      }}>
        <h2 style={{ marginBottom: '0.25rem', color: 'var(--text-primary)' }}>DB Creator</h2>
        <p style={{ marginBottom: '1.5rem', color: 'var(--text-muted)', fontSize: 13 }}>
          Enterprise Provisioning Platform
        </p>

        <div style={{ display: 'flex', gap: 4, marginBottom: '1.5rem' }}>
          {(['login', 'register'] as Mode[]).map(m => (
            <button
              key={m}
              onClick={() => { setMode(m); setError('') }}
              style={{
                flex: 1, padding: '6px 0', borderRadius: 4, border: 'none', cursor: 'pointer',
                background: mode === m ? 'var(--accent)' : 'var(--bg-tertiary)',
                color: mode === m ? '#fff' : 'var(--text-muted)',
                fontSize: 13, fontWeight: mode === m ? 600 : 400,
              }}
            >
              {m === 'login' ? 'Sign In' : 'Register'}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: 'var(--text-muted)' }}>
              Username
            </label>
            <input
              value={username}
              onChange={e => setUsername(e.target.value)}
              required
              autoFocus
              style={{ width: '100%', padding: '8px 10px', borderRadius: 4, boxSizing: 'border-box' }}
            />
          </div>

          {mode === 'register' && (
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: 'var(--text-muted)' }}>
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                style={{ width: '100%', padding: '8px 10px', borderRadius: 4, boxSizing: 'border-box' }}
              />
            </div>
          )}

          <div>
            <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: 'var(--text-muted)' }}>
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              style={{ width: '100%', padding: '8px 10px', borderRadius: 4, boxSizing: 'border-box' }}
            />
          </div>

          {error && (
            <p style={{ color: 'var(--danger)', fontSize: 12, margin: 0 }}>{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              padding: '9px 0', borderRadius: 4, border: 'none', cursor: loading ? 'not-allowed' : 'pointer',
              background: 'var(--accent)', color: '#fff', fontWeight: 600, fontSize: 14,
              opacity: loading ? 0.7 : 1,
            }}
          >
            {loading ? 'Please wait…' : mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>
        </form>
      </div>
    </div>
  )
}
