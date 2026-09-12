import { useState } from 'react'
import { authConfigured, supabase } from '../lib/supabase'

export interface SessionInfo {
  email: string
  token: string
}

interface Props {
  session: SessionInfo | null
  onSession: (s: SessionInfo | null) => void
}

export default function AuthPanel({ session, onSession }: Props) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  if (!authConfigured || !supabase) {
    return (
      <p className="muted small auth-note">
        Console login is not configured on this deployment — use developer mode (API key) below.
      </p>
    )
  }
  const sb = supabase // narrowed non-null; closures capture this local

  const submit = async () => {
    setError(null)
    setNotice(null)
    setBusy(true)
    try {
      const result =
        mode === 'signin'
          ? await sb.auth.signInWithPassword({ email, password })
          : await sb.auth.signUp({ email, password })
      if (result.error) throw result.error
      if (mode === 'signup') {
        setNotice('Check your inbox to confirm your email, then sign in.')
      }
      // onAuthStateChange in App picks up the session on success.
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const google = async () => {
    setError(null)
    const { error: err } = await sb.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin },
    })
    if (err) setError(err.message)
  }

  const signOut = async () => {
    await sb.auth.signOut()
    onSession(null)
  }

  if (session) {
    return (
      <div className="auth-signed-in">
        <span className="chip">
          <span className="dot completed" />
          {session.email}
        </span>
        <button className="ghost" onClick={signOut}>
          Sign out
        </button>
      </div>
    )
  }

  return (
    <div className="auth-panel">
      <div className="auth-tabs">
        <button className={mode === 'signin' ? 'ghost active' : 'ghost'} onClick={() => setMode('signin')}>
          Sign in
        </button>
        <button className={mode === 'signup' ? 'ghost active' : 'ghost'} onClick={() => setMode('signup')}>
          Create account
        </button>
      </div>

      {error && <div className="banner error">{error}</div>}
      {notice && <div className="banner info">{notice}</div>}

      <label className="field">
        <span>Email</span>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
      </label>
      <label className="field">
        <span>Password</span>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
        />
      </label>

      <button className="primary auth-submit" disabled={!email || !password || busy} onClick={submit}>
        {busy ? 'Working…' : mode === 'signin' ? 'Sign in' : 'Create account'}
      </button>

      <div className="auth-divider">
        <span className="muted small">or</span>
      </div>
      <button className="ghost auth-google" onClick={google}>
        Continue with Google
      </button>

      <p className="muted small">
        Free tier: a few forecasts per day on us — or run unlimited with your own key in developer mode.
      </p>
    </div>
  )
}
