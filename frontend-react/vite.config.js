import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
    // Vite 8 (rolldown) needs explicit extension order for production builds
    extensions: ['.mjs', '.js', '.jsx', '.ts', '.tsx', '.json'],
  },
  server: {
    port: 5173,
    // SPA: serve index.html for all unknown routes (client-side routing)
    historyApiFallback: true,
    proxy: {
      '/api': {
        target: 'https://nexora-ai-2-foxj.onrender.com',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  preview: {
    port: 4173,
    // Needed so direct navigation to /login, /workspace, etc. works
    historyApiFallback: true,
  },
})
