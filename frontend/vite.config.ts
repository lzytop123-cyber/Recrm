import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    // Compile React islands (Lanyard, backgrounds); leave .vue to the Vue plugin.
    react({ include: /[/\\](lanyard|backgrounds)[/\\].*\.[tj]sx?$/ }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  assetsInclude: ['**/*.glb'],
  server: {
    host: '0.0.0.0', // 允许同一局域网访问；
    port: 5173,
    proxy: {
      // 开发期把 /api 代理到本机 FastAPI
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/uploads': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  optimizeDeps: {
    include: ['react', 'react-dom', '@react-three/fiber', '@react-three/drei', '@react-three/rapier', 'three', 'meshline', 'ogl'],
  },
})
