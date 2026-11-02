import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev proxy: the web app calls the exact same endpoints as external
// developers on the API server. The target honors API_PORT so a developer
// who moved the API (e.g. to dodge a busy port, the same variable
// docker-compose uses) keeps a working proxy.
const apiPort = process.env.API_PORT || '8000'
const apiTarget = `http://localhost:${apiPort}`
const API_ROUTES = ['/companies', '/forecasts', '/stats', '/quota', '/config', '/health', '/ready']

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: Object.fromEntries(API_ROUTES.map((route) => [route, apiTarget])),
  },
})
