import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Mail, ArrowRight, Loader2, ArrowLeft, RefreshCw } from 'lucide-react';

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
  width: '44px', height: '54px', textAlign: 'center', fontSize: '22px',
  fontWeight: 700, borderRadius: '10px', outline: 'none',
  border: '1.5px solid var(--gray-200)', background: 'var(--gray-50)',
  fontFamily: 'inherit', boxSizing: 'border-box',
};

export default function LoginPage() {
  const { login, verifyCode, resendVerification } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const verified = params.get('verified') === '1';

  // Étape 1 : email
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [step, setStep] = useState<'email' | 'code'>('email');

  // Étape 2 : code
  const [code, setCode] = useState(['', '', '', '', '', '']);
  const [resent, setResent] = useState(false);
  const codeRefs = Array.from({ length: 6 }, () => useState<HTMLInputElement | null>(null)[1]);

  async function handleEmail(e: FormEvent) {
    e.preventDefault();
    setError('');
    setBusy(true);
    const res = await login(email); // envoie le code
    setBusy(false);
    if (res.ok) setStep('code');
    else setError(res.error || 'Erreur.');
    return false;
  }

  function handleCodeInput(i: number, value: string) {
    if (!/^\d?$/.test(value)) return;
    const next = [...code];
    next[i] = value;
    setCode(next);
    if (value && i < 5) {
      const el = document.querySelector<HTMLInputElement>(`[data-code-idx="${i + 1}"]`);
      el?.focus();
    }
  }

  function handleCodePaste(e: React.ClipboardEvent) {
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (pasted.length === 6) {
      setCode(pasted.split(''));
      document.querySelector<HTMLInputElement>('[data-code-idx="5"]')?.focus();
    }
  }

  function handleCodeKey(i: number, e: React.KeyboardEvent) {
    if (e.key === 'Backspace' && !code[i] && i > 0)
      document.querySelector<HTMLInputElement>(`[data-code-idx="${i - 1}"]`)?.focus();
  }

  async function handleCodeSubmit(e: FormEvent) {
    e.preventDefault();
    const full = code.join('');
    if (full.length !== 6) { setError('Veuillez saisir les 6 chiffres.'); return; }
    setError('');
    setBusy(true);
    const res = await verifyCode(email, full);
    setBusy(false);
    if (res.ok) navigate('/home', { replace: true });
    else setError(res.error || 'Code invalide ou expiré.');
  }

  async function handleResend() {
    if (!email) return;
    await resendVerification(email);
    setResent(true);
    setTimeout(() => setResent(false), 3000);
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'white', padding: '0 16px' }}>
      <div style={{ width: '100%', maxWidth: '380px' }}>

        {step === 'email' ? (
          <>
            <Link to="/home" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '14px', color: 'var(--gray-500)', marginBottom: '32px', textDecoration: 'none' }}>
              <ArrowLeft size={15} /> Retour
            </Link>

            <h1 style={{ fontSize: '26px', fontWeight: 700, color: 'var(--gray-900)', margin: '0 0 4px', letterSpacing: '-0.02em' }}>Connexion</h1>
            <p style={{ fontSize: '14px', color: 'var(--gray-500)', margin: '0 0 32px' }}>
              Entrez votre email pour recevoir un code de connexion.
            </p>

            {verified && (
              <div style={{ marginBottom: '20px', padding: '12px', borderRadius: '10px', background: '#ecfdf5', color: '#065f46', border: '1px solid #a7f3d0', fontSize: '14px', fontWeight: 500 }}>
                ✅ Email vérifié — connectez-vous.
              </div>
            )}

            <form onSubmit={handleEmail} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {error && (
                <div style={{ padding: '12px', borderRadius: '10px', background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca', fontSize: '14px' }}>{error}</div>
              )}

              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--gray-700)', marginBottom: '6px' }}>Email</label>
                <div style={{ position: 'relative' }}>
                  <Mail size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--gray-400)' }} />
                  <input type="email" required autoFocus value={email}
                    onChange={e => setEmail(e.target.value)} placeholder="vous@exemple.com"
                    style={inputBase}
                    onFocus={e => { e.target.style.borderColor = 'var(--blue)'; e.target.style.background = 'white'; }}
                    onBlur={e => { e.target.style.borderColor = 'var(--gray-200)'; e.target.style.background = 'var(--gray-50)'; }}
                  />
                </div>
              </div>

              <button type="submit" disabled={busy} style={{ ...btnPrimary, opacity: busy ? 0.6 : 1 }}>
                {busy ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <ArrowRight size={16} />}
                Recevoir le code
              </button>

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', margin: '8px 0' }}>
                <div style={{ flex: 1, height: '1px', background: 'var(--gray-200)' }} />
                <span style={{ fontSize: '12px', color: 'var(--gray-400)' }}>ou</span>
                <div style={{ flex: 1, height: '1px', background: 'var(--gray-200)' }} />
              </div>

              <div id="google-signin-button" style={{ display: 'flex', justifyContent: 'center' }} />

              <p style={{ textAlign: 'center', fontSize: '13px', color: 'var(--gray-400)', margin: 0 }}>
                Pas de mot de passe nécessaire — un code sera envoyé à votre adresse.
              </p>
            </form>
          </>
        ) : (
          <>
            <button onClick={() => setStep('email')}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '14px', color: 'var(--gray-500)', marginBottom: '32px', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit', padding: 0 }}>
              <ArrowLeft size={15} /> Modifier l'email
            </button>

            <div style={{ textAlign: 'center', marginBottom: '32px' }}>
              <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '48px', height: '48px', borderRadius: '12px', background: 'var(--blue)', color: 'white', marginBottom: '16px' }}>
                <Mail size={22} />
              </div>
              <h1 style={{ fontSize: '26px', fontWeight: 700, color: 'var(--gray-900)', margin: '0 0 8px', letterSpacing: '-0.02em' }}>Vérifiez votre email</h1>
              <p style={{ fontSize: '14px', color: 'var(--gray-500)', margin: 0, lineHeight: 1.6 }}>
                Code envoyé à{' '}
                <span style={{ fontWeight: 600, color: 'var(--gray-700)' }}>{email}</span>
              </p>
            </div>

            <form onSubmit={handleCodeSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {error && (
                <div style={{ padding: '12px', borderRadius: '10px', background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca', fontSize: '14px' }}>{error}</div>
              )}

              <div style={{ display: 'flex', justifyContent: 'center', gap: '8px' }} onPaste={handleCodePaste}>
                {code.map((d, i) => (
                  <input key={i} data-code-idx={i}
                    type="text" inputMode="numeric" maxLength={1} value={d}
                    onChange={e => handleCodeInput(i, e.target.value)}
                    onKeyDown={e => handleCodeKey(i, e)}
                    onFocus={e => { e.target.style.borderColor = 'var(--blue)'; e.target.style.background = 'white'; }}
                    onBlur={e => { e.target.style.borderColor = 'var(--gray-200)'; e.target.style.background = 'var(--gray-50)'; }}
                    style={digitBase}
                    autoFocus={i === 0}
                  />
                ))}
              </div>

              <button type="submit" disabled={busy} style={{ ...btnPrimary, opacity: busy ? 0.6 : 1 }}>
                {busy ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <ArrowRight size={16} />}
                Se connecter
              </button>

              <div style={{ textAlign: 'center' }}>
                <button type="button" onClick={handleResend}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '14px', color: 'var(--gray-500)', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit' }}>
                  <RefreshCw size={14} style={resent ? { animation: 'spin 1s linear infinite' } : undefined} />
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
