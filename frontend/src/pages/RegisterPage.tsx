/**
 * Création de compte — nom (facultatif), e-mail, puis code de vérification.
 *
 * Cette page était une COPIE de `LoginPage` : mêmes sept constantes de style,
 * mêmes gestionnaires de focus, même widget de code à six chiffres (aux
 * attributs `data-ri` près), même bouton de renvoi. Tout cela vit désormais
 * dans `components/auth/`, écrit une fois.
 */
import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Mail, User, ArrowRight } from 'lucide-react';

import { useAuth } from '../contexts/AuthContext';
import AuthLayout from '../components/auth/AuthLayout';
import CodeStep from '../components/auth/CodeStep';
import Alert from '../components/ui/Alert';
import Button from '../components/ui/Button';
import Field from '../components/ui/Field';

const CODE_VIDE = ['', '', '', '', '', ''];

export default function RegisterPage() {
  const { register, verifyCode, resendVerification } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [step, setStep] = useState<'form' | 'code'>('form');
  const [code, setCode] = useState(CODE_VIDE);
  const [resent, setResent] = useState(false);

  async function handleRegister(e: FormEvent) {
    e.preventDefault(); setError(''); setBusy(true);
    const res = await register(email, name || undefined); setBusy(false);
    if (res.ok) setStep('code');
    else setError(res.error || t('auth.err_generic'));
  }

  async function submitCode(e: FormEvent) {
    e.preventDefault();
    const full = code.join('');
    if (full.length !== 6) { setError(t('auth.err_six_digits')); return; }
    setError(''); setBusy(true);
    const res = await verifyCode(email, full); setBusy(false);
    if (res.ok) navigate('/home', { replace: true });
    else setError(res.error || t('auth.err_code_invalid'));
  }

  async function doResend() {
    await resendVerification(email);
    setResent(true);
    setTimeout(() => setResent(false), 3000);
  }

  if (step === 'code') {
    return (
      <AuthLayout retour={{ label: t('auth.change_email'), onClick: () => setStep('form') }}>
        <CodeStep
          email={email} code={code} onCodeChange={setCode}
          onSubmit={submitCode} onResend={doResend} resent={resent}
          busy={busy} error={error}
          title={t('auth.verification')}
          submitLabel={t('auth.create_my_account')}
        />
      </AuthLayout>
    );
  }

  return (
    <AuthLayout retour={{ label: t('nav.home'), to: '/home' }}>
      <h1 className="auth-titre">{t('auth.create_account')}</h1>
      <p className="auth-sous-titre">{t('auth.register_subtitle')}</p>

      <form onSubmit={handleRegister} className="auth-form">
        {error && <Alert tone="error">{error}</Alert>}

        <Field
          label={t('auth.name')}
          aside={<span className="champ__facultatif">{t('auth.optional')}</span>}
          icon={<User size={15} />}
          type="text" autoFocus value={name}
          autoComplete="name"
          placeholder={t('auth.name_placeholder')}
          onChange={(e) => setName(e.target.value)}
        />

        <Field
          label={t('auth.email')}
          icon={<Mail size={15} />}
          type="email" required value={email}
          autoComplete="email"
          placeholder={t('auth.email_placeholder')}
          onChange={(e) => setEmail(e.target.value)}
        />

        <Button type="submit" variant="primary" size="lg" block
          loading={busy} icon={<ArrowRight size={15} />}>
          {t('auth.get_code')}
        </Button>
      </form>

      <p className="auth-pied">
        {t('auth.have_account')} <Link to="/login">{t('auth.sign_in')}</Link>
      </p>
    </AuthLayout>
  );
}
