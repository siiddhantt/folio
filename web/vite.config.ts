import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig(({ mode }) => {
  const settings = loadEnv(mode, '..', 'FOLIO_');
  const port = process.env.FOLIO_PORT || settings.FOLIO_PORT || '8000';
  return {
    plugins: [react(), tailwindcss()],
    resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
    server: {
      proxy: {
        '/api': {
          target: `http://127.0.0.1:${port}`,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
  };
});
