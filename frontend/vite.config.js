import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

// Destino del proxy de `/api` en desarrollo.
// Se puede cambiar con VITE_API_PROXY_TARGET sin tocar el codigo.
const objetivoApi = process.env.VITE_API_PROXY_TARGET ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    // Sin CORS (SPEC §3): el frontend y la API se sirven bajo el mismo origen.
    // En desarrollo, Vite hace de proxy hacia Django.
    proxy: {
      '/api': {
        target: objetivoApi,
        // IMPORTANTE: no reescribir el Host.
        // Django valida el CSRF comparando el Referer contra el Host de la
        // peticion. Con `changeOrigin: true` el Host pasaria a ser el del
        // backend (127.0.0.1:8000) mientras el Referer sigue siendo
        // http://localhost:5173, y todos los POST responderian 403 CSRF.
        changeOrigin: false,
      },
    },
  },
  build: {
    // Django sirve este `dist` con WhiteNoise: los assets deben tener nombre
    // con hash para poder cachearlos de forma agresiva.
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.test.js'],
    restoreMocks: true,
  },
})
