// vitest 4 부터 test 키는 'vitest/config' 의 defineConfig 에만 있다 — 'vite' 것을 쓰면 TS2769.
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: { '/api': 'http://localhost:8000' },   // Vite dev(5173) → FastAPI(8000)
  },
  build: { outDir: 'dist' },   // FastAPI 가 server/frontend/dist 를 정적 서빙 (main.py:78)
  test: { environment: 'node', include: ['src/**/*.spec.ts'] },
})
