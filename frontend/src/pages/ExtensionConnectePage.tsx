/**
 * Page d'arrivée après l'autorisation de l'extension. L'extension surveille
 * cet onglet et lit elle-même le fragment ; la page ne fait que prévenir
 * l'utilisateur. Le code contenu dans le fragment n'est jamais affiché.
 */
import { useTranslation } from 'react-i18next';
import { CheckCircle2 } from 'lucide-react';

import AuthLayout from '../components/auth/AuthLayout';
import Alert from '../components/ui/Alert';

export default function ExtensionConnectePage() {
  const { t } = useTranslation();
  const fragment = new URLSearchParams(window.location.hash.replace(/^#/, ''));
  const connecte = fragment.has('code');
  const refus = fragment.get('erreur') === 'refus';

  if (connecte) {
    return (
      <AuthLayout titre={t('extension_auth.done_title')}>
        <Alert tone="success">
          <CheckCircle2 size={15} aria-hidden /> {t('extension_auth.done')}
        </Alert>
      </AuthLayout>
    );
  }
  if (refus) {
    return (
      <AuthLayout titre={t('extension_auth.refused_title')}>
        <Alert tone="info">{t('extension_auth.refused')}</Alert>
      </AuthLayout>
    );
  }
  return (
    <AuthLayout titre={t('extension_auth.title')}>
      <Alert tone="error">{t('extension_auth.invalid')}</Alert>
    </AuthLayout>
  );
}
