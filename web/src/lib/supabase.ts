import { useEffect, useState } from 'react'
import type { SupabaseClient } from '@supabase/supabase-js'

// Console login runs through Supabase Auth. Its browser-safe settings come
// from the API at runtime (GET /config), so one built bundle works on every
// deployment. Build-time VITE_SUPABASE_* vars still win when set (local dev).
// Without either, the console falls back to developer mode (paste an API key).
// supabase-js is loaded only when login is actually configured.

interface AuthConfig {
  url: string
  key: string
}

async function resolveAuthConfig(): Promise<AuthConfig | null> {
  const url = import.meta.env.VITE_SUPABASE_URL as string | undefined
  const key = (import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY ?? import.meta.env.VITE_SUPABASE_ANON_KEY) as
    | string
    | undefined
  if (url && key) return { url, key }
  try {
    const resp = await fetch('/config')
    if (!resp.ok) return null
    const { auth } = (await resp.json()) as {
      auth?: { enabled: boolean; supabase_url: string | null; supabase_key: string | null }
    }
    return auth?.enabled && auth.supabase_url && auth.supabase_key
      ? { url: auth.supabase_url, key: auth.supabase_key }
      : null
  } catch {
    return null
  }
}

let client: Promise<SupabaseClient | null> | null = null

/** The shared Supabase client, or null when login isn't configured. */
export function getSupabase(): Promise<SupabaseClient | null> {
  client ??= resolveAuthConfig().then(async (cfg) => {
    if (!cfg) return null
    const { createClient } = await import('@supabase/supabase-js')
    return createClient(cfg.url, cfg.key)
  })
  return client
}

/** React view of getSupabase(): `loading` stays true until config resolves. */
export function useSupabase(): { supabase: SupabaseClient | null; loading: boolean } {
  const [state, setState] = useState<{ supabase: SupabaseClient | null; loading: boolean }>({
    supabase: null,
    loading: true,
  })
  useEffect(() => {
    let cancelled = false
    getSupabase().then((supabase) => {
      if (!cancelled) setState({ supabase, loading: false })
    })
    return () => {
      cancelled = true
    }
  }, [])
  return state
}
