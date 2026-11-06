/**
 * Ouverture de la fenêtre d'invitation depuis N'IMPORTE OÙ — même patron que
 * `supportBus` : une fonction globale + un hôte unique (`InviteModal`).
 */
type Listener = () => void;

let listeners: Listener[] = [];

/** Ouvre la fenêtre d'invitation. */
export function openInvite(): void {
  listeners.forEach((fn) => fn());
}

/** Abonne l'hôte (InviteModal). Renvoie la fonction de désabonnement. */
export function subscribeInvite(fn: Listener): () => void {
  listeners.push(fn);
  return () => { listeners = listeners.filter((f) => f !== fn); };
}
