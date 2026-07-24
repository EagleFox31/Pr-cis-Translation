import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.tsx';
import ErrorBoundary from './components/ErrorBoundary.tsx';
import { installGlobalErrorReporting } from './lib/errorReporting.ts';
import './index.css';
import './i18n.ts';

// Capteurs globaux AVANT le rendu : une erreur au tout premier montage compte
// autant que les autres.
installGlobalErrorReporting();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
