/**
 * Plans et droits associés — UNE seule définition.
 *
 * Ce qui distingue un compte payant d'un compte d'essai est une règle
 * PRODUIT, pas un détail d'affichage : elle décidait jusqu'ici de l'aperçu
 * assombri et du téléchargement verrouillé depuis un `useState(true)` figé
 * dans `Home.tsx`, jamais rebranché sur le plan réel — tout le monde, admin
 * compris, était traité en essai.
 *
 * Rappel : ceci ne PROTÈGE rien. Le frontend décide de ce qu'il MONTRE ; c'est
 * au backend de refuser ce qui doit l'être. Les deux doivent rester d'accord.
 */

/** Le seul plan sans droits. Tous les autres (starter, pro, enterprise, admin)
 *  sont payants — la liste vit côté backend (`PLAN_STORAGE`), on ne la duplique
 *  donc pas ici : on nomme l'EXCEPTION, pas l'ensemble. */
export const FREE_PLAN = 'free';

/** Un plan donne-t-il les droits complets (aperçu net, téléchargement) ? */
export function isPaidPlan(plan?: string | null): boolean {
  return !!plan && plan !== FREE_PLAN;
}

/**
 * Le document doit-il être présenté en mode ESSAI (aperçu assombri,
 * téléchargement verrouillé) ?
 *
 * Vrai pour un visiteur non connecté ET pour un compte `free`.
 */
export function isTrialFor(user?: { plan?: string | null } | null): boolean {
  return !isPaidPlan(user?.plan);
}
