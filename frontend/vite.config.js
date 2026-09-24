import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import fs from 'node:fs'

const FRONTEND_PORT = Number(process.env.FRONTEND_PORT || 5188)
const HTTPS_CERT = process.env.FRONTEND_HTTPS_CERT
const HTTPS_KEY = process.env.FRONTEND_HTTPS_KEY

if (Boolean(HTTPS_CERT) !== Boolean(HTTPS_KEY)) {
  throw new Error('FRONTEND_HTTPS_CERT 和 FRONTEND_HTTPS_KEY 必须同时设置')
}

const https = HTTPS_CERT && HTTPS_KEY
  ? {
      cert: fs.readFileSync(HTTPS_CERT),
      key: fs.readFileSync(HTTPS_KEY)
    }
  : undefined

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    host: '0.0.0.0',
    port: FRONTEND_PORT,
    strictPort: true,
    https,
    proxy: {
      '/api': {
        target: 'http://localhost:8888',
        changeOrigin: true
      }
    }
  }
})
