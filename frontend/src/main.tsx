import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.tsx';
import ErrorBoundary from './components/ErrorBoundary.tsx';
import { installGlobalErrorReporting } from './lib/errorReporting.ts';
import './index.css';
import { languePrete } from './i18n.ts';
import { installerPrechargement, prechargerPage } from './lib/routes.ts';

// Capteurs globaux AVANT le rendu : une erreur au tout premier montage compte
// autant que les autres.
installGlobalErrorReporting();

// Page d'arrivée hors accueil (ex. `/extension`, prérendue) : son code est
// chargé AVANT le rendu, sinon React effacerait le contenu prérendu et
// laisserait un écran vide le temps du téléchargement.
installerPrechargement();
const pageArrivee = prechargerPage(location.pathname);

// Visiteur anglophone : on attend son dictionnaire (chargé à part) plutôt que
// d'afficher la page en français puis de la basculer.
Promise.all([languePrete.catch(() => { /* repli français */ }), pageArrivee]).finally(() => createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
));
