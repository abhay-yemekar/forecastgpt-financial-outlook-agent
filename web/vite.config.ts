import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev proxy: the web app calls the exact same endpoints as external
// developers — /companies and /forecasts on the API server.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/companies': 'http://localhost:8000',
      '/forecasts': 'http://localhost:8000',
    },
  },
})
