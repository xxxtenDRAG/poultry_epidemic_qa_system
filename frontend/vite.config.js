import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      // 开发环境将 /api 代理到 FastAPI 后端
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      // 开发环境将 /uploads 代理到 FastAPI 静态目录
      '/uploads': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
