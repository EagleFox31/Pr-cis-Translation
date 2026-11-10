/**
 * Fenêtre de paiement chargée à la demande : son code (et celui des moyens de
 * paiement) ne pèse sur le premier chargement que si l'utilisateur l'ouvre.
 * Une fois ouverte, elle reste montée pour garder son animation de fermeture.
 */
import { lazy, Suspense, useEffect, useState, type ComponentProps } from 'react';
import { avecReprise } from '../../lib/routes';

const chargerPaiement = avecReprise(() => import('./PaymentModal'));
const PaymentModal = lazy(chargerPaiement);

// Préchargée quand la page est au repos : le premier clic sur « Payer »
// s'ouvre sans délai, même sur un réseau lent, sans peser sur le démarrage.
let prechargee = false;
function prechargerAuRepos(): void {
  if (prechargee) return;
  prechargee = true;
  const lancer = () => { void chargerPaiement().catch(() => {}); };
  const w = window as Window & { requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number };
  if (w.requestIdleCallback) w.requestIdleCallback(lancer, { timeout: 5000 });
  else setTimeout(lancer, 3000);
}

type Props = ComponentProps<typeof import('./PaymentModal').default>;

export default function LazyPaymentModal(props: Props) {
  useEffect(prechargerAuRepos, []);
  const [monte, setMonte] = useState(props.open);
  if (props.open && !monte) setMonte(true);
  if (!monte) return null;
  return (
    <Suspense fallback={null}>
      <PaymentModal {...props} />
    </Suspense>
  );
}
