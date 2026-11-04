import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: { fs: { allow: ['../..'] }, proxy: { '/api': process.env.EDUSTUDIO_DEV_API_URL ?? 'http://localhost:8000' } },
})

