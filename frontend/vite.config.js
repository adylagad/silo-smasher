import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: { outDir: 'dist' },
  server: {
    proxy: {
      '/health':  'http://localhost:8000',
      '/diagnose':'http://localhost:8000',
      '/memory':  'http://localhost:8000',
      '/pipeline':'http://localhost:8000',
    },
  },
})
