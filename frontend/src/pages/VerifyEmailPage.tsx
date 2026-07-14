import { useState, useEffect, useRef, type FormEvent } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Mail, ArrowRight, Loader2, RefreshCw, ArrowLeft } from 'lucide-react';

const digitBase: React.CSSProperties = {
  width: '44px', height: '54px', textAlign: 'center', fontSize: '22px',
  fontWeight: 700, borderRadius: '10px', outline: 'none',
  border: '1.5px solid var(--gray-200)', background: 'var(--gray-50)',
  fontFamily: 'inherit', boxSizing: 'border-box',
};

const btnPrimary: React.CSSProperties = {
  width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
  gap: '8px', padding: '11px', borderRadius: '10px', border: 'none',
  background: 'var(--blue)', color: 'white', fontWeight: 600, fontSize: '14px',
  cursor: 'pointer', fontFamily: 'inherit',
};

export default function VerifyEmailPage() {
  const { verifyCode, resendVerification } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();

  const email = params.get('email') || '';
  const token = params.get('token');
  const [code, setCode] = useState(['', '', '', '', '', '']);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [resent, setResent] = useState(false);
  const [tokenVerified, setTokenVerified] = useState(false);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    if (!token || tokenVerified) return;
    setTokenVerified(true);
    (async () => {
      try {
        const API_BASE = (import.meta as any).env.VITE_API_BASE || 'http://127.0.0.1:8000';
        await fetch(`${API_BASE}/api/auth/verify-email?token=${encodeURIComponent(token)}`);
        navigate('/login?verified=1', { replace: true });
      } catch { /* le backend redirige */ }
    })();
  }, [token, tokenVerified, navigate]);

  function handleInput(i: number, value: string) {
    if (!/^\d?$/.test(value)) return;
    const next = [...code];
    next[i] = value;
    setCode(next);
    if (value && i < 5) inputRefs.current[i + 1]?.focus();
  }

  function handlePaste(e: React.ClipboardEvent) {
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (pasted.length === 6) { setCode(pasted.split('')); inputRefs.current[5]?.focus(); }
  }

  function handleKeyDown(i: number, e: React.KeyboardEvent) {
    if (e.key === 'Backspace' && !code[i] && i > 0) inputRefs.current[i - 1]?.focus();
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const fullCode = code.join('');
    if (fullCode.length !== 6) { setError('Veuillez saisir les 6 chiffres.'); return; }
    setError('');
    setBusy(true);
    const res = await verifyCode(email, fullCode);
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
        <Link to="/home" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '14px', color: 'var(--gray-500)', marginBottom: '32px', textDecoration: 'none' }}>
          <ArrowLeft size={15} /> Retour
        </Link>

        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '48px', height: '48px', borderRadius: '12px', background: 'var(--blue)', color: 'white', marginBottom: '16px' }}>
            <Mail size={22} />
          </div>
          <h1 style={{ fontSize: '26px', fontWeight: 700, color: 'var(--gray-900)', margin: '0 0 8px', letterSpacing: '-0.02em' }}>Vérifiez votre email</h1>
          <p style={{ fontSize: '14px', color: 'var(--gray-500)', margin: 0, lineHeight: 1.6 }}>
            Un code à 6 chiffres a été envoyé à{' '}
            <span style={{ fontWeight: 600, color: 'var(--gray-700)' }}>{email || 'votre adresse'}</span>
          </p>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {error && (
            <div style={{ padding: '12px', borderRadius: '10px', background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca', fontSize: '14px' }}>{error}</div>
          )}

          <div style={{ display: 'flex', justifyContent: 'center', gap: '8px' }} onPaste={handlePaste}>
            {code.map((d, i) => (
              <input key={i} ref={el => { inputRefs.current[i] = el; }}
                type="text" inputMode="numeric" maxLength={1} value={d}
                onChange={e => handleInput(i, e.target.value)}
                onKeyDown={e => handleKeyDown(i, e)}
                onFocus={e => { e.target.style.borderColor = 'var(--blue)'; e.target.style.background = 'white'; }}
                onBlur={e => { e.target.style.borderColor = 'var(--gray-200)'; e.target.style.background = 'var(--gray-50)'; }}
                style={{ ...digitBase, borderColor: i === 0 && !d ? 'var(--gray-200)' : undefined }}
                autoFocus={i === 0}
              />
            ))}
          </div>

          <button type="submit" disabled={busy} style={{ ...btnPrimary, opacity: busy ? 0.6 : 1 }}>
            {busy ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <ArrowRight size={16} />}
            Vérifier
          </button>

          <div style={{ textAlign: 'center' }}>
            <button type="button" onClick={handleResend}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '14px', color: 'var(--gray-500)', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit' }}>
              <RefreshCw size={14} style={resent ? { animation: 'spin 1s linear infinite' } : undefined} />
              {resent ? 'Code renvoyé !' : 'Renvoyer le code'}
            </button>
          </div>

          <p style={{ textAlign: 'center', fontSize: '14px', color: 'var(--gray-400)', margin: 0 }}>
            <Link to="/login" style={{ color: 'var(--gray-500)', textDecoration: 'none' }}>Retour à la connexion</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
