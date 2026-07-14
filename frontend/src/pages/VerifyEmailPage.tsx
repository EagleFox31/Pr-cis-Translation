import { useState, useEffect, useRef, type FormEvent } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Mail, ArrowRight, Loader2, RefreshCw, ArrowLeft } from 'lucide-react';

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

  // Lien cliqué → vérification automatique
  useEffect(() => {
    if (!token || tokenVerified) return;
    setTokenVerified(true);
    (async () => {
      try {
        const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';
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
    if (pasted.length === 6) {
      setCode(pasted.split(''));
      inputRefs.current[5]?.focus();
    }
  }

  function handleKeyDown(i: number, e: React.KeyboardEvent) {
    if (e.key === 'Backspace' && !code[i] && i > 0) {
      inputRefs.current[i - 1]?.focus();
    }
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

  const digitStyle = (focused: boolean) => ({
    border: focused ? '1.5px solid var(--blue)' : '1.5px solid var(--gray-200)',
    background: focused ? 'white' : 'var(--gray-50)',
  });

  return (
    <div className="min-h-screen flex items-center justify-center bg-white px-4">
      <div className="w-full max-w-sm">
        <Link to="/home"
          className="inline-flex items-center gap-1.5 text-sm mb-8"
          style={{ color: 'var(--gray-500)' }}
        >
          <ArrowLeft size={15} /> Retour
        </Link>

        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl mb-4"
            style={{ background: 'var(--blue)', color: 'white' }}>
            <Mail size={22} />
          </div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ color: 'var(--gray-900)' }}>
            Vérifiez votre email
          </h1>
          <p className="text-sm mt-2" style={{ color: 'var(--gray-500)' }}>
            Un code à 6 chiffres a été envoyé à{' '}
            <span className="font-semibold" style={{ color: 'var(--gray-700)' }}>
              {email || 'votre adresse'}
            </span>
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          {error && (
            <div className="p-3 rounded-lg text-sm"
              style={{ background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca' }}>
              {error}
            </div>
          )}

          <div className="flex justify-center gap-2" onPaste={handlePaste}>
            {code.map((d, i) => (
              <input key={i} ref={el => { inputRefs.current[i] = el; }}
                type="text" inputMode="numeric" maxLength={1} value={d}
                onChange={e => handleInput(i, e.target.value)}
                onKeyDown={e => handleKeyDown(i, e)}
                onFocus={e => Object.assign(e.target.style, digitStyle(true))}
                onBlur={e => Object.assign(e.target.style, digitStyle(false))}
                className="w-11 h-14 text-center text-xl font-bold rounded-lg outline-none transition-colors"
                style={digitStyle(i === 0)}
                autoFocus={i === 0}
              />
            ))}
          </div>

          <button type="submit" disabled={busy}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-semibold transition-all"
            style={{ background: 'var(--blue)', color: 'white', opacity: busy ? 0.6 : 1 }}>
            {busy ? <Loader2 size={16} className="animate-spin" /> : <ArrowRight size={16} />}
            Vérifier
          </button>

          <div className="text-center">
            <button type="button" onClick={handleResend}
              className="inline-flex items-center gap-1.5 text-sm transition-colors"
              style={{ color: 'var(--gray-500)' }}>
              <RefreshCw size={14} className={resent ? 'animate-spin' : ''} />
              {resent ? 'Code renvoyé !' : 'Renvoyer le code'}
            </button>
          </div>

          <p className="text-center text-sm" style={{ color: 'var(--gray-400)' }}>
            <Link to="/login" style={{ color: 'var(--gray-500)' }}>Retour à la connexion</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
