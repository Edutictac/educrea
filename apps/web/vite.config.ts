import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: { fs: { allow: ['../..'] }, proxy: {
    // Keep the browser's Host header: the API compares it with Origin before opening an anonymous session.
    '/api': { target: process.env.EDUCREA_DEV_API_URL ?? 'http://localhost:8000', changeOrigin: false },
  } },
})

