/**
 * Aller vers une section de l'accueil depuis N'IMPORTE OÙ — même patron que
 * `supportBus` : une fonction globale + un hôte unique (`Home`) qui s'y abonne.
 *
 * Pourquoi pas `scrollIntoView` directement : l'aperçu est une surcouche FIXE.
 * Défiler pendant qu'il est ouvert fait bouger la page DESSOUS, rien ne change
 * à l'écran. L'hôte ferme d'abord l'aperçu, puis défile vers la cible.
 */
type Listener = (sectionId: string) => void;

let listeners: Listener[] = [];

/** Amène la section `sectionId` à l'écran (en fermant l'aperçu au besoin). */
export function goToSection(sectionId: string): void {
  if (listeners.length === 0) {
    document.getElementById(sectionId)?.scrollIntoView({ behavior: 'smooth' });
    return;
  }
  listeners.forEach((fn) => fn(sectionId));
}

/** Abonne l'hôte (Home). Renvoie la fonction de désabonnement. */
export function subscribeSection(fn: Listener): () => void {
  listeners.push(fn);
  return () => { listeners = listeners.filter((l) => l !== fn); };
}
