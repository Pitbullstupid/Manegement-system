import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Mọi request bắt đầu bằng /api sẽ được Vite chuyển tiếp sang Django
      '/api': {
        target: 'http://127.0.0.1:8000', // dùng 127.0.0.1 thay localhost để tránh lỗi IPv6
        changeOrigin: true,
      },
    },
  },
})
