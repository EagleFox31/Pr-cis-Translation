import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Mail, ArrowRight, Loader2, ArrowLeft, RefreshCw, Sparkles } from 'lucide-react';
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
  const { login, verifyCode, resendVerification } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const verified = params.get('verified') === '1';

  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [step, setStep] = useState<'email' | 'code'>('email');
  const [code, setCode] = useState(['', '', '', '', '', '']);
  const [resent, setResent] = useState(false);

  async function handleEmail(e: FormEvent) {
    e.preventDefault(); setError(''); setBusy(true);
    const res = await login(email); setBusy(false);
    if (res.ok) setStep('code'); else setError(res.error || 'Erreur.');
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
    setError(''); setBusy(true);
    const res = await verifyCode(email, full); setBusy(false);
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
              Recevez un code de connexion par email.
            </p>

            {verified && (
              <div style={{ marginBottom: '16px', padding: '10px 12px', borderRadius: '10px', background: '#ecfdf5', color: '#065f46', border: '1px solid #a7f3d0', fontSize: '13px', fontWeight: 500 }}>
                ✅ Email vérifié — connectez-vous.
              </div>
            )}

            <form onSubmit={handleEmail} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {error && <div style={{ padding: '10px 12px', borderRadius: '10px', background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca', fontSize: '13px' }}>{error}</div>}

              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--gray-700)', marginBottom: '5px' }}>Email</label>
                <div style={{ position: 'relative' }}>
                  <Mail size={15} style={{ position: 'absolute', left: '11px', top: '50%', transform: 'translateY(-50%)', color: 'var(--gray-400)' }} />
                  <input type="email" required autoFocus value={email}
                    onChange={e => setEmail(e.target.value)} placeholder="vous@exemple.com"
                    style={inputBase} onFocus={focusIn} onBlur={focusOut} />
                </div>
              </div>

              <button type="submit" disabled={busy} style={{ ...btnPrimary, opacity: busy ? 0.6 : 1 }}>
                {busy ? <Loader2 size={15} style={{ animation: 'spin 1s linear infinite' }} /> : <ArrowRight size={15} />}
                Recevoir le code
              </button>

              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', margin: '4px 0' }}>
                <div style={{ flex: 1, height: '1px', background: 'var(--gray-200)' }} /><span style={{ fontSize: '11px', color: 'var(--gray-400)' }}>ou</span><div style={{ flex: 1, height: '1px', background: 'var(--gray-200)' }} />
              </div>

              <div id="google-signin-button" style={{ display: 'flex', justifyContent: 'center' }} />

              <p style={{ textAlign: 'center', fontSize: '13px', color: 'var(--gray-400)', margin: 0, lineHeight: 1.5 }}>
                Pas de mot de passe. Un code à 6 chiffres vous sera envoyé.
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
              <h1 style={{ fontSize: '22px', fontWeight: 700, color: 'var(--gray-900)', margin: '0 0 4px' }}>Vérification</h1>
              <p style={{ fontSize: '14px', color: 'var(--gray-500)', margin: 0, lineHeight: 1.5 }}>
                Code envoyé à <span style={{ fontWeight: 600, color: 'var(--gray-700)' }}>{email}</span>
              </p>
            </div>

            <form onSubmit={submitCode} style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
              {error && <div style={{ padding: '10px 12px', borderRadius: '10px', background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca', fontSize: '13px' }}>{error}</div>}

              <div style={{ display: 'flex', justifyContent: 'center', gap: '8px' }} onPaste={pasteCode}>
                {code.map((d, i) => (
                  <input key={i} data-ci={i} type="text" inputMode="numeric" maxLength={1} value={d}
                    onChange={e => handleCode(i, e.target.value)} onKeyDown={e => keyCode(i, e)}
                    onFocus={focusIn} onBlur={focusOut} style={digitBase} autoFocus={i === 0} />
                ))}
              </div>

              <button type="submit" disabled={busy} style={{ ...btnPrimary, opacity: busy ? 0.6 : 1 }}>
                {busy ? <Loader2 size={15} style={{ animation: 'spin 1s linear infinite' }} /> : <ArrowRight size={15} />}
                Se connecter
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
