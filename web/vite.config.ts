import { defineConfig, loadEnv, normalizePath } from 'vite';
import { createRequire } from 'node:module';
import path from 'node:path';
import { viteStaticCopy } from 'vite-plugin-static-copy';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath, URL } from 'node:url';

const require = createRequire(import.meta.url);
const pdfDirectory = path.dirname(require.resolve('pdfjs-dist/package.json'));

export default defineConfig(({ mode }) => {
  const settings = loadEnv(mode, '..', 'FOLIO_');
  const port = process.env.FOLIO_PORT || settings.FOLIO_PORT || '8000';
  return {
    plugins: [
      react(),
      tailwindcss(),
      viteStaticCopy({
        targets: ['cmaps', 'standard_fonts', 'wasm', 'iccs'].map((directory) => ({
          src: normalizePath(path.join(pdfDirectory, directory, '*')),
          dest: `pdf-assets/${directory}`,
          rename: { stripBase: true },
        })),
      }),
    ],
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
