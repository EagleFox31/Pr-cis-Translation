/**
 * Ouverture des fenêtres « Nouveautés » depuis N'IMPORTE OÙ — même patron que
 * `inviteBus` : une fonction globale + un hôte unique (`NouveautesModal`).
 */
import type { AVoir } from '../../hooks/useNouveautes';

export type ModeNouveautes = 'accueil' | 'depuis';
export type Demande = { mode: ModeNouveautes; donnees?: AVoir };
type Listener = (d: Demande) => void;

let listeners: Listener[] = [];
// Hôte chargé à la demande : une demande antérieure à son arrivée lui est remise.
let enAttente: Demande | null = null;

/**
 * Ouvre la visite d'accueil ou la fenêtre « depuis votre dernière visite ».
 * `donnees` : réponse déjà reçue de `/a-voir` (sinon l'hôte la demande).
 */
export function openNouveautes(mode: ModeNouveautes, donnees?: AVoir): void {
  const d: Demande = { mode, donnees };
  if (listeners.length === 0) { enAttente = d; return; }
  listeners.forEach((fn) => fn(d));
}

/** Abonne l'hôte (NouveautesModal). Renvoie la fonction de désabonnement. */
export function subscribeNouveautes(fn: Listener): () => void {
  listeners.push(fn);
  if (enAttente) { const d = enAttente; enAttente = null; fn(d); }
  return () => { listeners = listeners.filter((f) => f !== fn); };
}
