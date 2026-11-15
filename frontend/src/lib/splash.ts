/**
 * L'écran de démarrage ne s'affiche qu'à la toute première visite, et
 * seulement sur l'accueil : jamais sur une page ouverte depuis un lien
 * (connexion, e-mail, administration, extension).
 *
 * Calculé une seule fois au chargement du module : React peut appeler un
 * initialiseur d'état deux fois (StrictMode, rendu abandonné), et l'écriture
 * du marqueur dans un tel appel masquerait l'écran dès la première visite.
 */
const CLE = 'precis.splash.vu';
const ACCUEIL = new Set(['/', '/home']);

function calculer(): boolean {
  if (!ACCUEIL.has(window.location.pathname)) return false;
  try {
    if (localStorage.getItem(CLE)) return false;
    localStorage.setItem(CLE, '1');
  } catch {
    // Stockage indisponible (navigation privée stricte) : pas d'écran plutôt
    // qu'un écran à chaque chargement.
    return false;
  }
  return true;
}

export const SPLASH_ATTENDU = calculer();
