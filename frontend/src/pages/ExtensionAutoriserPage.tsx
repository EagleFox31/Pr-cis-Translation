/**
 * Autorisation de l'extension : l'utilisateur, connecté au site, accorde (ou
 * refuse) l'accès de son compte à l'extension qui l'a envoyé ici.
 *
 * Le `challenge` (PKCE) et le `state` viennent de l'extension ; ils sont
 * validés au format avant tout usage. Le code délivré par le serveur repart
 * dans le FRAGMENT (#) de l'adresse de retour : il n'atteint jamais un journal
 * de serveur et n'est jamais affiché.
 */
import { useState } from 'react';
import { Navigate, useLocation, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { useAuth } from '../contexts/AuthContext';
import api from '../services/api';
import AuthLayout from '../components/auth/AuthLayout';
import Alert from '../components/ui/Alert';
import Button from '../components/ui/Button';
import { extensionAuthParams } from '../lib/authReturn';

export default function ExtensionAutoriserPage() {
  const { t } = useTranslation();
  const { user, loading } = useAuth();
  const { pathname, search } = useLocation();
  const [params] = useSearchParams();
  const found = extensionAuthParams(params);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  if (!found) {
    return (
      <AuthLayout titre={t('extension_auth.title')}>
        <Alert tone="error">{t('extension_auth.invalid')}</Alert>
      </AuthLayout>
    );
  }
  if (loading) return null;
  if (!user) {
    return <Navigate to={`/login?next=${encodeURIComponent(pathname + search)}`} replace />;
  }

  async function autoriser() {
    if (!found) return;
    setError(''); setBusy(true);
    try {
      const res = await api.post('/api/extension/auth/code', { code_challenge: found.challenge });
      const data = res.data as { code?: string } | null;
      if (res.ok && data?.code) {
        window.location.replace(
          `/extension/connecte#code=${encodeURIComponent(data.code)}&state=${found.state}`);
        return;
      }
      setError(res.status === 403 ? t('extension_auth.unverified') : t('extension_auth.error'));
    } catch {
      setError(t('extension_auth.error'));
    }
    setBusy(false);
  }

  function annuler() {
    if (!found) return;
    window.location.replace(`/extension/connecte#erreur=refus&state=${found.state}`);
  }

  return (
    <AuthLayout titre={t('extension_auth.title')}>
      <div className="auth-form">
        {error && <Alert tone="error">{error}</Alert>}
        <p className="auth-sous-titre">{t('extension_auth.account', { email: user.email })}</p>
        <p className="auth-sous-titre">{t('extension_auth.body')}</p>
        <Button variant="primary" size="lg" block loading={busy} onClick={autoriser}>
          {t('extension_auth.allow')}
        </Button>
        <Button variant="secondary" size="lg" block disabled={busy} onClick={annuler}>
          {t('extension_auth.cancel')}
        </Button>
      </div>
    </AuthLayout>
  );
}
