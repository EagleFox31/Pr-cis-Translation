import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.tsx';
import ErrorBoundary from './components/ErrorBoundary.tsx';
import { installGlobalErrorReporting } from './lib/errorReporting.ts';
import './index.css';
import { languePrete } from './i18n.ts';

// Capteurs globaux AVANT le rendu : une erreur au tout premier montage compte
// autant que les autres.
installGlobalErrorReporting();

// Visiteur anglophone : on attend son dictionnaire (chargé à part) plutôt que
// d'afficher la page en français puis de la basculer.
languePrete.catch(() => { /* repli français */ }).finally(() => createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
));
