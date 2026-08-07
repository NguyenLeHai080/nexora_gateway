import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/router-embed': {
        target: 'http://127.0.0.1:20128',
        changeOrigin: false,
        xfwd: true,
        rewrite: (path) => path.replace(/^\/router-embed/, ''),
      },
      '/_next': { target: 'http://127.0.0.1:20128', changeOrigin: false },
      '/favicon.svg': { target: 'http://127.0.0.1:20128', changeOrigin: false },
      '/favicon.ico': { target: 'http://127.0.0.1:20128', changeOrigin: false },
      '/manifest.webmanifest': { target: 'http://127.0.0.1:20128', changeOrigin: false },
      '/provider-icons': { target: 'http://127.0.0.1:20128', changeOrigin: false },
    },
  },
});
