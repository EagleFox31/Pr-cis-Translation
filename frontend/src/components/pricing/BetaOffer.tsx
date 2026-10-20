import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useBetaProgram } from '../../hooks/useBetaProgram';
import BetaProgramDetails from './BetaProgramDetails';

export default function BetaOffer() {
  const { t } = useTranslation();
  const { program, error } = useBetaProgram();
  return (
    <aside className="pricing-card beta-offer" aria-label={t('beta.title')}>
      {program ? <BetaProgramDetails program={program} /> : <>
        <h3>{t('beta.title')}</h3>
        <p role={error ? 'alert' : 'status'}>{t(error ? 'beta.error' : 'beta.loading')}</p>
      </>}
      <div className="beta-actions">
        <Link className="beta-primary" to="/beta">
          {t(program?.applications_open ? 'beta.public.apply' : 'beta.public.discover')}
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
