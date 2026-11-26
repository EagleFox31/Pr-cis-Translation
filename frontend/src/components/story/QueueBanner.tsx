import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useReducedMotion } from 'motion/react';

export interface QueueEta {
  /** Début estimé, en secondes, au moment de la réception. */
  attenteS: number;
  /** Au-delà, rester vague (« plus de X min ») ; `null` = toujours chiffrer. */
  seuilS: number | null;
  /** `Date.now()` à la réception : sert à décompter le temps écoulé. */
  recuA: number;
}

/** Bandeau « en file d'attente » : position, puis début estimé (arrondi à la
 *  minute supérieure, vague au-delà du seuil). Recalculé toutes les 30 s. */
export default function QueueBanner({ ahead, eta }: { ahead: number; eta: QueueEta | null }) {
  const { t } = useTranslation();
  const reduire = useReducedMotion();
  const [maintenant, setMaintenant] = useState(() => Date.now());

  useEffect(() => {
    if (!eta) return;
    setMaintenant(Date.now());
    const id = window.setInterval(() => setMaintenant(Date.now()), 30_000);
    return () => window.clearInterval(id);
  }, [eta]);

  const position = ahead > 0 ? t('story.queued_ahead', { count: ahead }) : t('story.queued_next');
  let debut: string;
  let fermer = false;
  if (!eta) {
    debut = t('story.queued_wait');
  } else {
    const restant = eta.attenteS - (maintenant - eta.recuA) / 1000;
    if (restant <= 0) {
      debut = t('story.queued_late');
    } else if (eta.seuilS !== null && restant > eta.seuilS) {
      debut = t('story.queued_eta_long', { count: Math.round(eta.seuilS / 60) });
      fermer = true;
    } else if (restant < 60) {
      debut = t('story.queued_eta_soon');
    } else {
      debut = t('story.queued_eta', { count: Math.ceil(restant / 60) });
    }
  }

  return (
    <div role="status" style={{
      display: 'flex', alignItems: 'center', gap: '12px',
      padding: '14px 18px', marginBottom: '16px', borderRadius: '12px',
      background: '#eff6ff', border: '1px solid #bfdbfe', color: '#1e40af',
      fontSize: '14px', lineHeight: 1.5,
    }}>
      <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
        style={{ flexShrink: 0, animation: reduire ? undefined : 'spin 1.2s linear infinite' }}>
        <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
      </svg>
      <span style={{ flex: 1 }}>
        {position} {debut}{fermer && <> {t('story.queued_close')}</>}
      </span>
    </div>
  );
}
