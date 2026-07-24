/**
 * Ouverture de la fenêtre d'assistance depuis N'IMPORTE OÙ — même patron
 * impératif que `showToast` : une fonction globale + un hôte unique monté une
 * fois qui s'y abonne (`SupportModal`).
 *
 * L'intérêt : référencer AUTOMATIQUEMENT le document concerné. Quand on signale
 * un problème depuis l'aperçu ou une carte de bibliothèque, on passe l'identité
 * du document en `prefill.document` — l'utilisateur n'a rien à retrouver ni à
 * retaper, et l'admin sait tout de suite DE QUEL document il s'agit.
 */
export type SupportCategory = 'problem' | 'subscription' | 'other';

export interface SupportPrefill {
  category?: SupportCategory;
  /** Document concerné (référencement automatique). `id` peut manquer côté
   *  aperçu d'une traduction fraîche ; le `name` suffit à identifier. */
  document?: { id?: string; name?: string };
}

type Listener = (prefill: SupportPrefill) => void;

let listeners: Listener[] = [];

/** Ouvre la fenêtre d'assistance, éventuellement pré-remplie. */
export function openSupport(prefill: SupportPrefill = {}): void {
  listeners.forEach((fn) => fn(prefill));
}

/** Abonne l'hôte (SupportModal). Renvoie la fonction de désabonnement. */
export function subscribeSupport(fn: Listener): () => void {
  listeners.push(fn);
  return () => { listeners = listeners.filter((f) => f !== fn); };
}
