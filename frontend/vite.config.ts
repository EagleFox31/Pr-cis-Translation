import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { readFileSync } from 'fs';
import path from 'path';
import { defineConfig } from 'vite';

// Forme OBJET et non fonction : la forme fonction faisait inférer `boolean` là
// où Vite attend `true | string[]` (`allowedHosts`), et tsc refusait la config.
// Version du ZIP servi par /extension (installation manuelle) : celle du
// manifest de l'extension voisine ; vide si le dossier n'est pas là.
function versionExtension(): string {
  try {
    return JSON.parse(readFileSync(path.resolve(__dirname, '../extension/manifest.json'), 'utf8')).version ?? '';
  } catch {
    return '';
  }
}

export default defineConfig({
  define: {
    __EXTENSION_VERSION__: JSON.stringify(process.env.VITE_EXTENSION_ZIP_VERSION ?? versionExtension()),
  },
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
