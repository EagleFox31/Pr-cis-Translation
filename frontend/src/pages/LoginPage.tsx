/**
 * Connexion — mot de passe, code par e-mail, ou Google.
 *
 * CE QUI A ÉTÉ RETIRÉ DE L'ÉCRAN
 * ------------------------------
 * Une phrase disait, SOUS le bouton Google : « Pas de mot de passe. Un code à
 * 6 chiffres vous sera envoyé. » Placée là, elle semblait décrire Google. Elle
 * décrivait en réalité le lien « Recevoir plutôt un code par email », trois
 * rangs plus haut — qui le dit déjà. Une phrase de trop, et trompeuse.
 *
 * Le sous-titre annonçait lui aussi les deux voies (« Entrez votre mot de
 * passe, ou recevez un code ») que les commandes en dessous proposent. Trois
 * formulations de la même chose : il n'en reste qu'une, sur le lien lui-même.
 *
 * Et la marque n'apparaît plus qu'UNE fois — deux logos se suivaient.
 */
import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { GoogleLogin } from '@react-oauth/google';
import { Mail, ArrowRight, Lock, CheckCircle2 } from 'lucide-react';

import { useAuth } from '../contexts/AuthContext';
import AuthLayout from '../components/auth/AuthLayout';
import CodeStep from '../components/auth/CodeStep';
import Alert from '../components/ui/Alert';
import Button from '../components/ui/Button';
import Field from '../components/ui/Field';

const CODE_VIDE = ['', '', '', '', '', ''];

export default function LoginPage() {
  const { login, verifyCode, resendVerification, googleAuth,
          loginPassword, forgotPassword, resetPassword } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const verified = params.get('verified') === '1';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  // 'email' : connexion par mot de passe (défaut) · 'code' : saisie du code
  // reçu — il sert AUSSI BIEN à la connexion sans mot de passe qu'à la
  // réinitialisation, d'où `codeFor` qui dit quoi faire une fois le code saisi.
  const [step, setStep] = useState<'email' | 'code'>('email');
  const [codeFor, setCodeFor] = useState<'login' | 'reset'>('login');
  const [newPassword, setNewPassword] = useState('');
  const [code, setCode] = useState(CODE_VIDE);
  const [resent, setResent] = useState(false);
  const [googleBusy, setGoogleBusy] = useState(false);

  /** Connexion par MOT DE PASSE — session ouverte sans passer par la boîte mail. */
  async function handlePassword(e: FormEvent) {
    e.preventDefault(); setError(''); setInfo(''); setBusy(true);
    const res = await loginPassword(email, password); setBusy(false);
    if (res.ok) navigate('/home', { replace: true });
    else setError(res.error || t('auth.err_credentials'));
  }

  /** Repli : recevoir un code par e-mail (compte sans mot de passe). */
  async function handleEmailCode() {
    if (!email) { setError(t('auth.err_email_required')); return; }
    setError(''); setInfo(''); setBusy(true);
    const res = await login(email); setBusy(false);
    if (res.ok) { setCodeFor('login'); setStep('code'); }
    else setError(res.error || t('auth.err_generic'));
  }

  /** Mot de passe oublié : on revérifie l'email, puis on réinitialise. */
  async function handleForgot() {
    if (!email) { setError(t('auth.err_email_for_code')); return; }
    setError(''); setBusy(true);
    await forgotPassword(email); setBusy(false);
    setCodeFor('reset'); setStep('code'); setCode(CODE_VIDE);
    setInfo(t('auth.info_code_sent_if_account'));
  }

  async function submitCode(e: FormEvent) {
    e.preventDefault();
    const full = code.join('');
    if (full.length !== 6) { setError(t('auth.err_six_digits')); return; }
    if (codeFor === 'reset' && newPassword.length < 10) {
      setError(t('auth.err_password_short')); return;
    }
    setError(''); setBusy(true);
    // Le même code prouve la possession de la boîte : il connecte, ou il
    // réinitialise, selon la porte par laquelle on est entré.
    const res = codeFor === 'reset'
      ? await resetPassword(email, full, newPassword)
      : await verifyCode(email, full);
    setBusy(false);
    if (res.ok) navigate('/home', { replace: true });
    else setError(res.error || t('auth.err_code_invalid'));
  }

  async function doResend() {
    if (!email) return;
    await resendVerification(email);
    setResent(true);
    setTimeout(() => setResent(false), 3000);
  }

  if (step === 'code') {
    return (
      <AuthLayout retour={{ label: t('auth.change_email'), onClick: () => setStep('email') }}>
        <CodeStep
          email={email} code={code} onCodeChange={setCode}
          onSubmit={submitCode} onResend={doResend} resent={resent}
          busy={busy} error={error} info={info}
          title={codeFor === 'reset' ? t('auth.new_password') : t('auth.verification')}
          submitLabel={codeFor === 'reset' ? t('auth.change_password') : t('auth.sign_in')}
        >
          {codeFor === 'reset' && (
            <Field
              label={t('auth.new_password')}
              icon={<Lock size={15} />}
              type="password" required value={newPassword}
              autoComplete="new-password"
              placeholder={t('auth.password_placeholder')}
              hint={t('auth.password_hint')}
              onChange={(e) => setNewPassword(e.target.value)}
            />
          )}
        </CodeStep>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      retour={{ label: t('nav.home'), to: '/home' }}
      attente={googleBusy ? t('auth.signing_in') : null}
    >
      <h1 className="auth-titre">{t('auth.sign_in')}</h1>

      {verified && (
        <Alert tone="success">
          <CheckCircle2 size={15} aria-hidden /> {t('auth.email_verified')}
        </Alert>
      )}

      <form onSubmit={handlePassword} className="auth-form">
        {error && <Alert tone="error">{error}</Alert>}

        <Field
          label={t('auth.email')}
          icon={<Mail size={15} />}
          type="email" required autoFocus value={email}
          autoComplete="username"
          placeholder={t('auth.email_placeholder')}
          onChange={(e) => setEmail(e.target.value)}
        />

        <Field
          label={t('auth.password')}
          icon={<Lock size={15} />}
          type="password" required value={password}
          autoComplete="current-password"
          placeholder="••••••••••"
          aside={
            <button type="button" className="auth-lien" onClick={handleForgot} disabled={busy}>
              {t('auth.forgot_password')}
            </button>
          }
          onChange={(e) => setPassword(e.target.value)}
        />

        <Button type="submit" variant="primary" size="lg" block
          loading={busy} icon={<ArrowRight size={15} />}>
          {t('auth.sign_in')}
        </Button>

        {/* Repli : les comptes créés avant le mot de passe n'en ont pas. */}
        <button type="button" className="auth-lien-discret" onClick={handleEmailCode} disabled={busy}>
          {t('auth.use_email_code')}
        </button>
      </form>

      <div className="auth-separateur"><span>{t('auth.or')}</span></div>

      <div className="auth-google">
        <GoogleLogin
          onSuccess={async (res) => {
            // Le retour de Google ferme sa popup et rend la main à une page en
            // apparence inerte : le seul indicateur était le bouton « Se
            // connecter », que ce chemin ne touche pas. Quelques secondes sans
            // le moindre signe se lisent comme un plantage, pas une attente.
            setError(''); setBusy(true); setGoogleBusy(true);
            const r = await googleAuth(res.credential!);
            setBusy(false); setGoogleBusy(false);
            if (r.ok) navigate('/home', { replace: true });
            else setError(r.error || t('auth.err_google'));
          }}
          onError={() => { setGoogleBusy(false); setError(t('auth.err_google')); }}
          theme="outline" size="large" text="continue_with" shape="pill" width="330"
        />
      </div>

      <p className="auth-pied">
        {t('auth.no_account')} <Link to="/register">{t('auth.create_account')}</Link>
      </p>
    </AuthLayout>
  );
}
