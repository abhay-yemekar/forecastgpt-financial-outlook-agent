import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev proxy: the web app calls the exact same endpoints as external
// developers — /companies and /forecasts on the API server. The target
// honors API_PORT so a developer who moved the API (e.g. to dodge a busy
// port, the same variable docker-compose uses) keeps a working proxy.
const apiPort = process.env.API_PORT || '8000'
const apiTarget = `http://localhost:${apiPort}`

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/companies': apiTarget,
      '/forecasts': apiTarget,
    },
  },
})
