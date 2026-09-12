import { createClient, type SupabaseClient } from '@supabase/supabase-js'

// Console login runs through Supabase Auth when the deployment configures
// VITE_SUPABASE_URL + VITE_SUPABASE_ANON_KEY. Without them the console
// falls back to developer mode (paste an API key).
const url = import.meta.env.VITE_SUPABASE_URL as string | undefined
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined

export const supabase: SupabaseClient | null =
  url && anonKey ? createClient(url, anonKey) : null

export const authConfigured = Boolean(supabase)
