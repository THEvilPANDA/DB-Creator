import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const API_TARGET = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: true,
    watch: { usePolling: true },
    proxy: {
      '/api': {
        target: API_TARGET,
        ws: true,
      },
      '/health': API_TARGET,
    },
  },
})
