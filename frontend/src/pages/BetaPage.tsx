import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { useBeta, type BetaFormat } from '../hooks/useBeta';
import { useBetaProgram } from '../hooks/useBetaProgram';
import api from '../services/api';
import AdminShell from '../components/admin/AdminShell';
import BetaAllowances, { BETA_FORMATS } from '../components/library/BetaAllowances';
import BetaProgramDetails from '../components/pricing/BetaProgramDetails';
import SupportModal from '../components/support/SupportModal';
import { openSupport } from '../components/support/supportBus';

function ApplicationForm({ onSubmitted }: { onSubmitted: () => Promise<void> }) {
  const { t } = useTranslation();
  const [format, setFormat] = useState<BetaFormat>('pdf');
  const [motivation, setMotivation] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  return <form onSubmit={event => {
    event.preventDefault(); setBusy(true); setError('');
    void (async () => {
      try {
        const result = await api.post('/api/beta/applications', { primary_format: format, motivation });
        if (result.ok) await onSubmitted();
        else {
          const detail = (result.data as { detail?: unknown })?.detail;
          setError(typeof detail === 'string' ? detail : t('beta.error'));
        }
      } catch { setError(t('beta.error')); }
      finally { setBusy(false); }
    })();
  }}>
    <fieldset disabled={busy} className="beta-fieldset beta-application-form">
      <label>{t('beta.primary_format')}<select value={format}
        onChange={event => setFormat(event.target.value as BetaFormat)}>
        {BETA_FORMATS.map(item => <option key={item} value={item}>{t(`beta.formats.${item}`)}</option>)}
      </select></label>
      <label>{t('beta.application.motivation')}<textarea required minLength={10} maxLength={1000} rows={4}
        value={motivation} onChange={event => setMotivation(event.target.value)}
        placeholder={t('beta.application.placeholder')} /></label>
      <p className="beta-note">{t('beta.application.commitment')}</p>
      <p className="beta-note">{t('beta.application.privacy_hint')}</p>
      {error && <p role="alert" className="beta-error">{error}</p>}
      <button className="beta-primary" type="submit">{t(busy ? 'beta.loading' : 'beta.application.submit')}</button>
    </fieldset>
  </form>;
}

export default function BetaPage() {
  const { t, i18n } = useTranslation();
  const { user, loading } = useAuth();
  const { data, error, refresh } = useBeta();
  const publicBeta = useBetaProgram();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const enrollment = data?.enrollment;
  const application = data?.application;

  const activate = async () => {
    setBusy(true); setMessage('');
    try {
      const result = await api.post('/api/beta/activate');
      if (result.ok) await refresh();
      else setMessage(String((result.data as { detail?: string })?.detail || t('beta.error')));
    } catch { setMessage(t('beta.error')); }
    finally { setBusy(false); }
  };

  return (
    <AdminShell title={t('beta.title')}>
      <section className="beta-public" aria-label={t('beta.title')}>
        {publicBeta.program ? <BetaProgramDetails program={publicBeta.program} heading="h2" /> : <>
          <h2>{t('beta.title')}</h2><p role={publicBeta.error ? 'alert' : 'status'}>
            {t(publicBeta.error ? 'beta.error' : 'beta.loading')}</p>
          {publicBeta.error && <button className="tb-btn" onClick={() => void publicBeta.refresh()}>{t('beta.refresh')}</button>}
        </>}
      </section>
      <section className="beta-card beta-intro">
        <h2>{t(enrollment ? 'beta.my_access' : 'beta.public.apply')}</h2>
        {!user && !loading ? (
          <><p>{t('beta.application.login_hint')}</p><Link className="beta-primary" to="/login?next=%2Fbeta">{t('beta.login')}</Link></>
        ) : error ? (
          <><p role="alert">{t('beta.error')}</p><button className="tb-btn" onClick={() => void refresh()}>{t('beta.refresh')}</button></>
        ) : !data ? (
          <p>{t('beta.loading')}</p>
        ) : !enrollment ? (
          application ? <>
            <p role="status"><span className="beta-status">{t(`beta.application.states.${application.state}`)}</span></p>
            <p>{t(`beta.application.messages.${application.state}`)}</p>
            <p className="beta-note">{t('beta.application.bound_email', { email: user?.email })}</p>
            <button className="tb-btn" onClick={() => void refresh()}>{t('beta.refresh')}</button>
          </> : !publicBeta.program ? <p>{t(publicBeta.error ? 'beta.error' : 'beta.loading')}</p>
            : !publicBeta.program.applications_open ? <p>{t(`beta.public.closed_hint.${publicBeta.program.availability}`)}</p>
            : !data.email_verified ? <>
              <p>{t('beta.application.verify_email')}</p>
              <Link className="beta-primary" to={'/verify-email?email=' + encodeURIComponent(user?.email || '') + '&next=%2Fbeta'}>
                {t('auth.verify')}
              </Link>
            </> : <>
              <p>{t('beta.application.bound_email', { email: user?.email })}</p>
              <ApplicationForm onSubmitted={refresh} />
            </>
        ) : (
          <>
            <p><span className={'beta-status beta-status--' + enrollment.state}>
              {t(`beta.states.${enrollment.state}`)}
            </span></p>
            <p>{t('beta.bound_email', { email: user?.email })}</p>
            {enrollment.state === 'invited' && <>
              <p>{t('beta.activation_hint', { days: data.access_days })}</p>
              {!data.email_verified && <p role="alert">{t('beta.verify_email')}</p>}
              {!data.can_activate && <p>{t('beta.activation_closed')}</p>}
              <button className="beta-primary" disabled={busy || !data.can_activate || !data.email_verified}
                onClick={() => void activate()}>{t(busy ? 'beta.loading' : 'beta.activate')}</button>
            </>}
            {enrollment.expires_at && <p>{t('beta.expires', {
              date: new Date(enrollment.expires_at).toLocaleString(i18n.language),
            })}</p>}
            <BetaAllowances enrollment={enrollment} />
            <p className="beta-note">{t('beta.quota_hint')}</p>
            {message && <p role="alert" className="beta-error">{message}</p>}
            <div className="beta-actions">
              <Link className="beta-primary" to="/home">{t('beta.translate')}</Link>
              <button className="tb-btn ghost" onClick={() => openSupport({
                category: 'other', subject: t('beta.feedback_subject'), message: t('beta.feedback_template'),
              })}>{t('beta.feedback')}</button>
            </div>
          </>
        )}
      </section>
      <SupportModal />
    </AdminShell>
  );
}
