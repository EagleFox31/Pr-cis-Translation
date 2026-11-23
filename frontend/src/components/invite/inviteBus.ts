/**
 * Ouverture de la fenêtre d'invitation depuis N'IMPORTE OÙ — même patron que
 * `supportBus` : une fonction globale + un hôte unique (`InviteModal`).
 */
type Listener = () => void;

let listeners: Listener[] = [];
// Hôte chargé à la demande : une demande antérieure à son arrivée lui est remise.
let enAttente = false;

/** Ouvre la fenêtre d'invitation. */
export function openInvite(): void {
  if (listeners.length === 0) { enAttente = true; return; }
  listeners.forEach((fn) => fn());
}

/** Abonne l'hôte (InviteModal). Renvoie la fonction de désabonnement. */
export function subscribeInvite(fn: Listener): () => void {
  listeners.push(fn);
  if (enAttente) { enAttente = false; fn(); }
  return () => { listeners = listeners.filter((f) => f !== fn); };
}
