/**
 * Paiement par carte — « Default payment link » déclaré chez Paddle.
 *
 * Paddle renvoie ici avec `?_ptxn=txn_…` (le `checkout_url` de la transaction
 * créée par le backend). La page est affichée dans le cadre de `PaymentModal` ;
 * le formulaire Paddle s'y loge en mode `inline`. Rien n'est crédité d'ici : la
 * confirmation arrive par le webhook, et la fenêtre la suit par son polling.
 */
import { useEffect, useRef, useState } from 'react';
import { Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { CARD_HEIGHT_MSG } from '../lib/cardPayment';

const PADDLE_JS = 'https://cdn.paddle.com/paddle/v2/paddle.js';
const PADDLE_ENV = import.meta.env.VITE_PADDLE_ENV as string | undefined;
const PADDLE_TOKEN = import.meta.env.VITE_PADDLE_CLIENT_TOKEN as string | undefined;
const FRAME_CLASS = 'paddle-checkout-frame';

type Phase = 'loading' | 'ready' | 'done' | 'error';

declare global {
  interface Window { Paddle?: any }
}

function loadPaddle(): Promise<any> {
  if (window.Paddle) return Promise.resolve(window.Paddle);
  return new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = PADDLE_JS;
    s.async = true;
    s.onload = () => (window.Paddle ? resolve(window.Paddle) : reject(new Error('Paddle.js absent')));
    s.onerror = () => reject(new Error('Paddle.js injoignable'));
    document.head.appendChild(s);
  });
}

export default function CardPaymentPage() {
  const [phase, setPhase] = useState<Phase>('loading');
  const [error, setError] = useState('');

  // Annonce la hauteur du contenu à la fenêtre de paiement, qui ajuste son
  // cadre : le formulaire Paddle grandit après son chargement.
  // On mesure le conteneur, pas le document : celui-ci prend la hauteur du
  // cadre et ne rétrécirait jamais.
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = root.current;
    if (window.parent === window || !el) return;
    const send = () => window.parent.postMessage(
      { type: CARD_HEIGHT_MSG, height: el.getBoundingClientRect().height },
      window.location.origin);
    const ro = new ResizeObserver(send);
    ro.observe(el);
    send();
    return () => ro.disconnect();
  }, []);

  // Lu une seule fois : l'effet retire `_ptxn` de l'URL, et React (mode strict
  // en dev) le rejoue aussitôt — il ne doit alors ni conclure à un lien
  // incomplet, ni ouvrir un second checkout.
  const [txn] = useState(() => new URLSearchParams(window.location.search).get('_ptxn'));
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    // Pas de valeur de repli : un oubli de configuration doit se voir.
    if (!PADDLE_TOKEN || (PADDLE_ENV !== 'sandbox' && PADDLE_ENV !== 'production')) {
      setError('Paiement par carte non configuré (VITE_PADDLE_ENV / VITE_PADDLE_CLIENT_TOKEN).');
      setPhase('error');
      return;
    }
    if (!txn) {
      setError('Lien de paiement incomplet : aucune transaction indiquée.');
      setPhase('error');
      return;
    }

    // Paddle ouvre seul le checkout quand l'URL porte `_ptxn` : on le retire
    // pour l'ouvrir nous-mêmes, une seule fois, avec nos réglages inline.
    const url = new URL(window.location.href);
    url.searchParams.delete('_ptxn');
    window.history.replaceState(null, '', url);

    loadPaddle().then((Paddle) => {
      if (PADDLE_ENV === 'sandbox') Paddle.Environment.set('sandbox');
      Paddle.Initialize({
        token: PADDLE_TOKEN,
        checkout: {
          settings: {
            displayMode: 'inline',
            frameTarget: FRAME_CLASS,
            frameInitialHeight: 450,
            frameStyle: 'width: 100%; min-width: 312px; background-color: transparent; border: none;',
            variant: 'one-page',
            locale: 'fr',
          },
        },
        // `checkout.error` n'est pas traité : Paddle affiche lui-même ses
        // erreurs dans le formulaire, qui doit rester visible.
        eventCallback: (ev: { name?: string }) => {
          if (ev.name === 'checkout.loaded') setPhase('ready');
          else if (ev.name === 'checkout.completed') setPhase('done');
        },
      });
      Paddle.Checkout.open({ transactionId: txn });
    }).catch(() => {
      setError('Impossible de charger le module de paiement. Réessayez plus tard.');
      setPhase('error');
    });
  }, [txn]);

  return (
    <div ref={root} style={{ background: '#f6f7f9', padding: '12px',
                  boxSizing: 'border-box', fontFamily: 'inherit' }}>
      {phase === 'loading' && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '48px 0', color: 'var(--blue)' }}>
          <Loader2 size={28} className="animate-spin" />
        </div>
      )}
      {phase === 'error' && (
        <div role="alert" style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '32px auto',
                                   maxWidth: 400, color: '#b91c1c', fontSize: '14px' }}>
          <AlertCircle size={18} /> {error}
        </div>
      )}
      {phase === 'done' && (
        <div style={{ textAlign: 'center', padding: '48px 0', fontSize: '15px' }}>
          <CheckCircle2 size={36} color="#16a34a" />
          <p style={{ margin: '12px 0 0', fontWeight: 600 }}>Paiement reçu</p>
          <p style={{ margin: '4px 0 0', color: 'var(--gray-500)', fontSize: '13px' }}>
            Confirmation en cours…
          </p>
        </div>
      )}
      {/* Toujours présent : Paddle y insère son cadre dès l'initialisation. */}
      <div className={FRAME_CLASS} style={{ display: phase === 'done' || phase === 'error' ? 'none' : 'block' }} />
    </div>
  );
}
