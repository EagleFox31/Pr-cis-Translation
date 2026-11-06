import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import type { BetaProgram } from '../../hooks/useBetaProgram';
import BetaProgramDetails from './BetaProgramDetails';

/** Carte Bêta des tarifs : affichée seulement si les candidatures sont ouvertes (cf. `PricingCards`). */
export default function BetaOffer({ program }: { program: BetaProgram }) {
  const { t } = useTranslation();
  return (
    <aside className="pricing-card beta-offer" aria-label={t('beta.title')}>
      <BetaProgramDetails program={program} />
      <div className="beta-actions">
        <Link className="beta-primary" to="/beta">
          {t('beta.public.apply')}
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"
            aria-hidden="true" focusable="false">
            <path d="M5 12h14m-5-5 5 5-5 5" />
          </svg>
        </Link>
      </div>
    </aside>
  );
}
