import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { defineConfig } from 'vite';

// Forme OBJET et non fonction : la forme fonction faisait inférer `boolean` là
// où Vite attend `true | string[]` (`allowedHosts`), et tsc refusait la config.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.'),
    },
  },
  server: {
    host: true,
    // En dev, `npm run dev` (scripts/dev.py) peut couper le rechargement à chaud.
    hmr: process.env.DISABLE_HMR !== 'true',
    allowedHosts: true,
    // L'interface et l'API sont ainsi de MÊME ORIGINE en développement : CORS
    // n'intervient pas du tout. Il ne concerne qu'un déploiement sur deux
    // domaines.
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
});
