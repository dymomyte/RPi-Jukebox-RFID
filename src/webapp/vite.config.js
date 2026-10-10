import { createHash } from 'node:crypto';
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const apiTarget = process.env.API_PROXY_TARGET || 'http://localhost:5556';

// Translation files keep their names across releases. Their content hash goes
// into the URL, so browsers that cached an older file still load the new texts.
const localesVersion = () => {
  const dir = 'public/locales';
  const hash = createHash('sha256');
  readdirSync(dir, { recursive: true })
    .filter((file) => file.endsWith('.json'))
    .sort()
    .forEach((file) => hash.update(file).update(readFileSync(join(dir, file))));
  return hash.digest('hex').slice(0, 12);
};

export default defineConfig({
  plugins: [react()],
  define: {
    'import.meta.env.VITE_LOCALES_VERSION': JSON.stringify(localesVersion()),
  },
  build: {
    outDir: 'build',
    sourcemap: false,
  },
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/api': {
        target: apiTarget,
        ws: true,
        changeOrigin: false,
      },
    },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{js,jsx}'],
    environmentOptions: {
      jsdom: {
        url: 'http://localhost/',
      },
    },
    setupFiles: ['./src/setupTests.js'],
  },
});
