/**
 * Vérification d'e-mail — arrivée depuis le lien reçu, ou saisie du code.
 *
 * TROISIÈME copie du même écran, après `LoginPage` et `RegisterPage` : mêmes
 * constantes de style, même widget à six chiffres (ici en `data-vi`), même
 * bouton de renvoi. Elle utilise maintenant `CodeStep`, comme les deux autres.
 */
import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { useAuth } from '../contexts/AuthContext';
import AuthLayout from '../components/auth/AuthLayout';
import CodeStep from '../components/auth/CodeStep';

export default function VerifyEmailPage() {
  const { verifyCode, resendVerification } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [params] = useSearchParams();

  const email = params.get('email') || '';
  const token = params.get('token');

  const [code, setCode] = useState(['', '', '', '', '', '']);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [resent, setResent] = useState(false);

  // Vérification par LIEN : redirection navigateur, pas de fetch — le backend
  // redirige lui-même vers /login?verified=1, et aucun CORS n'entre en jeu.
  useEffect(() => {
    if (!token) return;
    window.location.href = `/api/auth/verify-email?token=${encodeURIComponent(token)}`;
  }, [token]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const full = code.join('');
    if (full.length !== 6) { setError(t('auth.err_six_digits')); return; }
    setError(''); setBusy(true);
    const res = await verifyCode(email, full); setBusy(false);
    if (res.ok) navigate('/home', { replace: true });
    else setError(typeof res.error === 'string' ? res.error : t('auth.err_code_invalid'));
  }

  async function doResend() {
    if (!email) return;
    await resendVerification(email);
    setResent(true);
    setTimeout(() => setResent(false), 3000);
  }

  return (
    <AuthLayout retour={{ label: t('nav.home'), to: '/home' }}>
      <CodeStep
        email={email || t('auth.your_address')}
        code={code} onCodeChange={setCode}
        onSubmit={submit} onResend={doResend} resent={resent}
        busy={busy} error={error}
        title={t('auth.verification')}
        submitLabel={t('auth.verify')}
      />
    </AuthLayout>
  );
}
