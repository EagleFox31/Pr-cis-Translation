/**
 * Fenêtre de paiement chargée à la demande : son code (et celui des moyens de
 * paiement) ne pèse sur le premier chargement que si l'utilisateur l'ouvre.
 * Une fois ouverte, elle reste montée pour garder son animation de fermeture.
 */
import { lazy, Suspense, useState, type ComponentProps } from 'react';

const PaymentModal = lazy(() => import('./PaymentModal'));

type Props = ComponentProps<typeof import('./PaymentModal').default>;

export default function LazyPaymentModal(props: Props) {
  const [monte, setMonte] = useState(props.open);
  if (props.open && !monte) setMonte(true);
  if (!monte) return null;
  return (
    <Suspense fallback={null}>
      <PaymentModal {...props} />
    </Suspense>
  );
}
