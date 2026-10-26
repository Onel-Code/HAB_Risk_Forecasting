import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  server: { proxy: { '/auto-forecast': 'http://127.0.0.1:8000','/predict': 'http://127.0.0.1:8000',} },
  plugins: [react()],
})
