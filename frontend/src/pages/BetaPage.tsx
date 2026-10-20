import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { useBeta } from '../hooks/useBeta';
import api from '../services/api';
import AdminShell from '../components/admin/AdminShell';
import BetaAllowances from '../components/library/BetaAllowances';
import SupportModal from '../components/support/SupportModal';
import { openSupport } from '../components/support/supportBus';

export default function BetaPage() {
  const { t, i18n } = useTranslation();
  const { user, loading } = useAuth();
  const { data, error, refresh } = useBeta();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const enrollment = data?.enrollment;

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
    <AdminShell title={t('beta.my_access')}>
      <div className="beta-card beta-intro">
        <h2>{data?.campaign_name || t('beta.title')}</h2>
        {!user && !loading ? (
          <><p>{t('beta.login_hint')}</p><Link className="tb-btn" to="/login">{t('beta.login')}</Link></>
        ) : error ? (
          <p role="alert">{t('beta.error')}</p>
        ) : !data ? (
          <p>{t('beta.loading')}</p>
        ) : !enrollment ? (
          <p>{t('beta.no_invitation')}</p>
        ) : (
          <>
            <p><span className={'beta-status beta-status--' + enrollment.state}>
              {t(`beta.states.${enrollment.state}`)}
            </span></p>
            <p>{t('beta.bound_email', { email: user?.email })}</p>
            {enrollment.state === 'invited' && (
              <>
                <p>{t('beta.activation_hint', { days: data.access_days })}</p>
                {!data.email_verified && <p role="alert">{t('beta.verify_email')}</p>}
                {!data.can_activate && <p>{t('beta.activation_closed')}</p>}
                <button className="tb-btn" disabled={busy || !data.can_activate || !data.email_verified}
                  onClick={() => void activate()}>{busy ? t('beta.loading') : t('beta.activate')}</button>
              </>
            )}
            {enrollment.expires_at && <p>{t('beta.expires', {
              date: new Date(enrollment.expires_at).toLocaleString(i18n.language),
            })}</p>}
            <BetaAllowances enrollment={enrollment} />
            <p className="beta-note">{t('beta.quota_hint')}</p>
            {message && <p role="alert" className="beta-error">{message}</p>}
            <div className="beta-actions">
              <Link className="tb-btn" to="/home">{t('beta.translate')}</Link>
              <button className="tb-btn ghost" onClick={() => openSupport({
                category: 'other', subject: t('beta.feedback_subject'), message: t('beta.feedback_template'),
              })}>
                {t('beta.feedback')}
              </button>
            </div>
          </>
        )}
      </div>
      <SupportModal />
    </AdminShell>
  );
}
