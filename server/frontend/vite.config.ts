/// <reference types="vitest" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: { '/api': 'http://localhost:8000' },   // Vite dev(5173) → FastAPI(8000)
  },
  build: { outDir: 'dist' },   // FastAPI 가 server/frontend/dist 를 정적 서빙 (main.py:78)
  test: { environment: 'node', include: ['src/**/*.spec.ts'] },
})
