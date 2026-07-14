import { useState, useEffect, useRef, type FormEvent } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Mail, ArrowRight, Loader2, RefreshCw } from 'lucide-react';

export default function VerifyEmailPage() {
  const { verifyCode, resendVerification } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();

  const email = params.get('email') || '';
  const token = params.get('token'); // du lien

  const [code, setCode] = useState(['', '', '', '', '', '']);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [resent, setResent] = useState(false);
  const [tokenVerified, setTokenVerified] = useState(false);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  // Vérification automatique par lien (token dans l'URL)
  useEffect(() => {
    if (!token || tokenVerified) return;
    (async () => {
      setTokenVerified(true);
      try {
        const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';
        await fetch(`${API_BASE}/api/auth/verify-email?token=${encodeURIComponent(token)}`);
        navigate('/login?verified=1', { replace: true });
      } catch { /* le backend redirige déjà */ }
    })();
  }, [token, tokenVerified, navigate]);

  function handleInput(i: number, value: string) {
    if (!/^\d?$/.test(value)) return; // chiffres seulement
    const next = [...code];
    next[i] = value;
    setCode(next);
    // Auto-avance au champ suivant
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

  return (
    <div className="min-h-screen flex items-center justify-center bg-neutral-50 px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 bg-neutral-900 text-white rounded-xl mb-4">
            <Mail size={22} />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-neutral-900">Vérifiez votre email</h1>
          <p className="text-sm text-neutral-500 mt-2">
            Un code à 6 chiffres a été envoyé à{' '}
            <span className="font-medium text-neutral-700">{email || 'votre adresse'}</span>
          </p>
        </div>

        <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border border-neutral-200 p-6 space-y-5">
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
          )}

          {/* 6 champs de code */}
          <div className="flex justify-center gap-2" onPaste={handlePaste}>
            {code.map((d, i) => (
              <input
                key={i}
                ref={el => { inputRefs.current[i] = el; }}
                type="text"
                inputMode="numeric"
                maxLength={1}
                value={d}
                onChange={e => handleInput(i, e.target.value)}
                onKeyDown={e => handleKeyDown(i, e)}
                className="w-11 h-14 text-center text-xl font-bold border border-neutral-300 rounded-lg focus:ring-2 focus:ring-neutral-900 focus:border-neutral-900 outline-none"
                autoFocus={i === 0}
              />
            ))}
          </div>

          <button type="submit" disabled={busy}
            className="w-full flex items-center justify-center gap-2 bg-neutral-900 text-white py-2.5 rounded-lg text-sm font-medium hover:bg-neutral-800 disabled:opacity-50 transition-colors">
            {busy ? <Loader2 size={16} className="animate-spin" /> : <ArrowRight size={16} />}
            Vérifier
          </button>

          <div className="text-center">
            <button type="button" onClick={handleResend}
              className="inline-flex items-center gap-1.5 text-sm text-neutral-500 hover:text-neutral-700 transition-colors">
              <RefreshCw size={14} className={resent ? 'animate-spin' : ''} />
              {resent ? 'Code renvoyé !' : 'Renvoyer le code'}
            </button>
          </div>

          <p className="text-center text-sm text-neutral-400">
            <Link to="/login" className="hover:text-neutral-600">Retour à la connexion</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
