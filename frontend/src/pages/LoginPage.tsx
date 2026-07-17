import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Mail, ArrowRight, Loader2, ArrowLeft, RefreshCw, Sparkles, Lock } from 'lucide-react';
import { GoogleLogin } from '@react-oauth/google';
import AuthBackground from '../components/auth/AuthBackground';

const logo = '/Logo.png';
const identityImg = '/Identite Precis.png';

/* ── Styles partagés ─────────────────────────────────────────────────── */

const pageStyle: React.CSSProperties = {
  minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
  background: 'linear-gradient(160deg, #f8fafc 0%, #eef2ff 40%, #f0f4ff 100%)',
  padding: '24px 16px', fontFamily: 'inherit',
};

const cardStyle: React.CSSProperties = {
  width: '100%', maxWidth: '400px', background: 'white',
  borderRadius: '20px', boxShadow: '0 1px 3px rgba(0,0,0,.04), 0 8px 32px rgba(0,0,0,.06)',
  border: '1px solid var(--gray-100)', padding: '36px 28px 32px',
};

const logoStyle: React.CSSProperties = {
  width: '40px', height: '40px', borderRadius: '10px',
  boxShadow: '0 2px 8px rgba(26,77,199,.15)',
};

const inputBase: React.CSSProperties = {
  width: '100%', padding: '10px 12px 10px 38px', borderRadius: '10px',
  fontSize: '14px', outline: 'none', border: '1.5px solid var(--gray-200)',
  background: 'var(--gray-50)', fontFamily: 'inherit', boxSizing: 'border-box',
};

const btnPrimary: React.CSSProperties = {
  width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
  gap: '8px', padding: '11px', borderRadius: '10px', border: 'none',
  background: 'var(--blue)', color: 'white', fontWeight: 600, fontSize: '14px',
  cursor: 'pointer', fontFamily: 'inherit',
};

const digitBase: React.CSSProperties = {
  width: '46px', height: '56px', textAlign: 'center', fontSize: '22px',
  fontWeight: 700, borderRadius: '10px', outline: 'none',
  border: '1.5px solid var(--gray-200)', background: 'var(--gray-50)',
  fontFamily: 'inherit', boxSizing: 'border-box',
};

const focusIn = (e: React.FocusEvent<HTMLInputElement>) => {
  e.target.style.borderColor = 'var(--blue)'; e.target.style.background = 'white';
};
const focusOut = (e: React.FocusEvent<HTMLInputElement>) => {
  e.target.style.borderColor = 'var(--gray-200)'; e.target.style.background = 'var(--gray-50)';
};

/* ── Composant ────────────────────────────────────────────────────────── */

export default function LoginPage() {
  const { login, verifyCode, resendVerification, googleAuth,
          loginPassword, forgotPassword, resetPassword } = useAuth();
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
  const [code, setCode] = useState(['', '', '', '', '', '']);
  const [resent, setResent] = useState(false);

  /** Connexion par MOT DE PASSE — session ouverte sans passer par la boîte mail. */
  async function handlePassword(e: FormEvent) {
    e.preventDefault(); setError(''); setInfo(''); setBusy(true);
    const res = await loginPassword(email, password); setBusy(false);
    if (res.ok) navigate('/home', { replace: true });
    else setError(res.error || 'Email ou mot de passe incorrect.');
  }

  /** Repli : recevoir un code par email (compte sans mot de passe). */
  async function handleEmailCode() {
    if (!email) { setError('Saisissez votre email.'); return; }
    setError(''); setInfo(''); setBusy(true);
    const res = await login(email); setBusy(false);
    if (res.ok) { setCodeFor('login'); setStep('code'); }
    else setError(res.error || 'Erreur.');
  }

  /** Mot de passe oublié : on revérifie l'email, puis on réinitialise. */
  async function handleForgot() {
    if (!email) { setError('Saisissez votre email pour recevoir un code.'); return; }
    setError(''); setBusy(true);
    await forgotPassword(email); setBusy(false);
    setCodeFor('reset'); setStep('code'); setCode(['', '', '', '', '', '']);
    setInfo('Si un compte existe pour cet email, un code vient d’être envoyé.');
  }

  function handleCode(i: number, v: string) {
    if (!/^\d?$/.test(v)) return;
    const n = [...code]; n[i] = v; setCode(n);
    if (v && i < 5) document.querySelector<HTMLInputElement>(`[data-ci="${i + 1}"]`)?.focus();
  }
  function pasteCode(e: React.ClipboardEvent) {
    const p = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (p.length === 6) { setCode(p.split('')); document.querySelector<HTMLInputElement>('[data-ci="5"]')?.focus(); }
  }
  function keyCode(i: number, e: React.KeyboardEvent) {
    if (e.key === 'Backspace' && !code[i] && i > 0) document.querySelector<HTMLInputElement>(`[data-ci="${i - 1}"]`)?.focus();
  }
  async function submitCode(e: FormEvent) {
    e.preventDefault();
    const full = code.join('');
    if (full.length !== 6) { setError('Veuillez saisir les 6 chiffres.'); return; }
    if (codeFor === 'reset' && newPassword.length < 10) {
      setError('Le nouveau mot de passe doit faire au moins 10 caractères.'); return;
    }
    setError(''); setBusy(true);
    // Le même code prouve la possession de la boîte : il connecte, ou il
    // réinitialise, selon la porte par laquelle on est entré.
    const res = codeFor === 'reset'
      ? await resetPassword(email, full, newPassword)
      : await verifyCode(email, full);
    setBusy(false);
    if (res.ok) navigate('/home', { replace: true });
    else setError(res.error || 'Code invalide ou expiré.');
  }
  async function doResend() { if (!email) return; await resendVerification(email); setResent(true); setTimeout(() => setResent(false), 3000); }

  return (
    <div style={pageStyle}>
      <AuthBackground />
      <div style={{ ...cardStyle, position: 'relative', zIndex: 1 }}>
        {/* En-tête — logo animé à gauche, image identité à droite */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '28px' }}>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <img src={logo} alt="P" style={{ height: '46px', width: 'auto' }} />
            <span className="animated-logo-text">récis</span>
          </div>
          <img src={identityImg} alt="Précis" style={{ height: '48px', width: 'auto', opacity: 0.9 }} />
        </div>

        {step === 'email' ? (
          <>
            <Link to="/home" style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', fontSize: '13px', color: 'var(--gray-400)', marginBottom: '20px', textDecoration: 'none' }}>
              <ArrowLeft size={14} /> Accueil
            </Link>

            <h1 style={{ fontSize: '22px', fontWeight: 700, color: 'var(--gray-900)', margin: '0 0 4px' }}>Connexion</h1>
            <p style={{ fontSize: '14px', color: 'var(--gray-500)', margin: '0 0 ' + (verified ? '12px' : '20px'), lineHeight: 1.5 }}>
              Entrez votre mot de passe, ou recevez un code par email.
            </p>

            {verified && (
              <div style={{ marginBottom: '16px', padding: '10px 12px', borderRadius: '10px', background: '#ecfdf5', color: '#065f46', border: '1px solid #a7f3d0', fontSize: '13px', fontWeight: 500 }}>
                ✅ Email vérifié — connectez-vous.
              </div>
            )}

            <form onSubmit={handlePassword} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {error && <div style={{ padding: '10px 12px', borderRadius: '10px', background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca', fontSize: '13px' }}>{error}</div>}

              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--gray-700)', marginBottom: '5px' }}>Email</label>
                <div style={{ position: 'relative' }}>
                  <Mail size={15} style={{ position: 'absolute', left: '11px', top: '50%', transform: 'translateY(-50%)', color: 'var(--gray-400)' }} />
                  <input type="email" required autoFocus value={email} autoComplete="username"
                    onChange={e => setEmail(e.target.value)} placeholder="vous@exemple.com"
                    style={inputBase} onFocus={focusIn} onBlur={focusOut} />
                </div>
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '5px' }}>
                  <label style={{ fontSize: '13px', fontWeight: 500, color: 'var(--gray-700)' }}>Mot de passe</label>
                  <button type="button" onClick={handleForgot} disabled={busy}
                    style={{ background: 'none', border: 'none', padding: 0, fontSize: '12px', color: 'var(--blue)', cursor: 'pointer' }}>
                    Mot de passe oublié ?
                  </button>
                </div>
                <div style={{ position: 'relative' }}>
                  <Lock size={15} style={{ position: 'absolute', left: '11px', top: '50%', transform: 'translateY(-50%)', color: 'var(--gray-400)' }} />
                  <input type="password" required value={password} autoComplete="current-password"
                    onChange={e => setPassword(e.target.value)} placeholder="••••••••••"
                    style={inputBase} onFocus={focusIn} onBlur={focusOut} />
                </div>
              </div>

              <button type="submit" disabled={busy} style={{ ...btnPrimary, opacity: busy ? 0.6 : 1 }}>
                {busy ? <Loader2 size={15} style={{ animation: 'spin 1s linear infinite' }} /> : <ArrowRight size={15} />}
                Se connecter
              </button>

              {/* Repli : les comptes créés avant le mot de passe n'en ont pas. */}
              <button type="button" onClick={handleEmailCode} disabled={busy}
                style={{ background: 'none', border: 'none', padding: 0, fontSize: '12.5px', color: 'var(--gray-500)', cursor: 'pointer', textDecoration: 'underline' }}>
                Recevoir plutôt un code par email
              </button>

              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', margin: '4px 0' }}>
                <div style={{ flex: 1, height: '1px', background: 'var(--gray-200)' }} /><span style={{ fontSize: '11px', color: 'var(--gray-400)' }}>ou</span><div style={{ flex: 1, height: '1px', background: 'var(--gray-200)' }} />
              </div>

              <div style={{ display: 'flex', justifyContent: 'center', overflow: 'hidden' }}>
                <GoogleLogin
                  onSuccess={async (res) => {
                    setError(''); setBusy(true);
                    const r = await googleAuth(res.credential!);
                    setBusy(false);
                    if (r.ok) navigate('/home', { replace: true });
                    else setError(r.error || 'Erreur Google.');
                  }}
                  onError={() => setError('Erreur lors de la connexion Google.')}
                  theme="outline"
                  size="large"
                  text="continue_with"
                  shape="pill"
                  width="328"
                />
              </div>

              <p style={{ textAlign: 'center', fontSize: '13px', color: 'var(--gray-400)', margin: 0, lineHeight: 1.5 }}>
                Pas de mot de passe. Un code à 6 chiffres vous sera envoyé.
              </p>

              <p style={{ textAlign: 'center', fontSize: '14px', margin: 0 }}>
                <Link to="/register" style={{ color: 'var(--blue)', fontWeight: 600, textDecoration: 'none' }}>Créer un compte</Link>
              </p>
            </form>
          </>
        ) : (
          <>
            <button onClick={() => setStep('email')}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', fontSize: '13px', color: 'var(--gray-400)', marginBottom: '20px', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit', padding: 0 }}>
              <ArrowLeft size={14} /> Modifier l'email
            </button>

            <div style={{ textAlign: 'center', marginBottom: '24px' }}>
              <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '44px', height: '44px', borderRadius: '12px', background: 'var(--blue)', color: 'white', marginBottom: '12px' }}>
                <Sparkles size={20} />
              </div>
              <h1 style={{ fontSize: '22px', fontWeight: 700, color: 'var(--gray-900)', margin: '0 0 4px' }}>
                {codeFor === 'reset' ? 'Nouveau mot de passe' : 'Vérification'}
              </h1>
              <p style={{ fontSize: '14px', color: 'var(--gray-500)', margin: 0, lineHeight: 1.5 }}>
                Code envoyé à <span style={{ fontWeight: 600, color: 'var(--gray-700)' }}>{email}</span>
              </p>
            </div>

            {info && (
              <div style={{ marginBottom: '14px', padding: '10px 12px', borderRadius: '10px', background: '#eff6ff', color: '#1e40af', border: '1px solid #bfdbfe', fontSize: '12.5px' }}>
                {info}
              </div>
            )}

            <form onSubmit={submitCode} style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
              {error && <div style={{ padding: '10px 12px', borderRadius: '10px', background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca', fontSize: '13px' }}>{error}</div>}

              <div style={{ display: 'flex', justifyContent: 'center', gap: '8px' }} onPaste={pasteCode}>
                {code.map((d, i) => (
                  <input key={i} data-ci={i} type="text" inputMode="numeric" maxLength={1} value={d}
                    onChange={e => handleCode(i, e.target.value)} onKeyDown={e => keyCode(i, e)}
                    onFocus={focusIn} onBlur={focusOut} style={digitBase} autoFocus={i === 0} />
                ))}
              </div>

              {codeFor === 'reset' && (
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--gray-700)', marginBottom: '5px' }}>
                    Nouveau mot de passe
                  </label>
                  <div style={{ position: 'relative' }}>
                    <Lock size={15} style={{ position: 'absolute', left: '11px', top: '50%', transform: 'translateY(-50%)', color: 'var(--gray-400)' }} />
                    <input type="password" required value={newPassword} autoComplete="new-password"
                      onChange={e => setNewPassword(e.target.value)} placeholder="10 caractères minimum"
                      style={inputBase} onFocus={focusIn} onBlur={focusOut} />
                  </div>
                  <p style={{ fontSize: '11.5px', color: 'var(--gray-400)', margin: '6px 0 0' }}>
                    Une phrase longue vaut mieux qu'un mot compliqué.
                  </p>
                </div>
              )}

              <button type="submit" disabled={busy} style={{ ...btnPrimary, opacity: busy ? 0.6 : 1 }}>
                {busy ? <Loader2 size={15} style={{ animation: 'spin 1s linear infinite' }} /> : <ArrowRight size={15} />}
                {codeFor === 'reset' ? 'Changer le mot de passe' : 'Se connecter'}
              </button>

              <div style={{ textAlign: 'center' }}>
                <button type="button" onClick={doResend}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', fontSize: '13px', color: 'var(--gray-400)', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit' }}>
                  <RefreshCw size={13} style={resent ? { animation: 'spin 1s linear infinite' } : undefined} />
                  {resent ? 'Code renvoyé !' : 'Renvoyer le code'}
                </button>
              </div>
            </form>
          </>
        )}
      </div>
    </div>
  );
}


