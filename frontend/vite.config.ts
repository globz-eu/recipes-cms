import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/frontend/',
  server: {
    proxy: {
      '/api': 'http://localhost:8080',
      '/api-auth': 'http://localhost:8080',
      '/login': 'http://localhost:8080',
      '/complete': 'http://localhost:8080',
      '/disconnect': 'http://localhost:8080',
      '/admin': 'http://localhost:8080',
      '/media': 'http://localhost:8080',
    },
  },
})
