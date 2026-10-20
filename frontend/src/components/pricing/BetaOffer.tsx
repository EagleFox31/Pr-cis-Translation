import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useBetaProgram } from '../../hooks/useBetaProgram';
import BetaProgramDetails from './BetaProgramDetails';

export default function BetaOffer() {
  const { t } = useTranslation();
  const { program, error } = useBetaProgram();
  return <aside className="beta-public beta-offer" aria-label={t('beta.title')}>
    {program ? <BetaProgramDetails program={program} /> : <>
      <h3>{t('beta.title')}</h3><p role={error ? 'alert' : 'status'}>{t(error ? 'beta.error' : 'beta.loading')}</p>
    </>}
    <div className="beta-actions">
      <Link className="beta-primary" to="/beta">{t(program?.applications_open ? 'beta.public.apply' : 'beta.public.discover')}</Link>
      <span className="beta-note">{t('beta.public.selection')}</span>
    </div>
  </aside>;
}
