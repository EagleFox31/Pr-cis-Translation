import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Mail, User, ArrowRight, Loader2, ArrowLeft, RefreshCw } from 'lucide-react';

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

export default function RegisterPage() {
  const { register, verifyCode, resendVerification } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [step, setStep] = useState<'form' | 'code'>('form');
  const [code, setCode] = useState(['', '', '', '', '', '']);
  const [resent, setResent] = useState(false);

  async function handleRegister(e: FormEvent) {
    e.preventDefault();
    setError('');
    setBusy(true);
    const res = await register(email, name || undefined);
    setBusy(false);
    if (res.ok) setStep('code');
    else setError(res.error || "Erreur lors de l'inscription.");
  }

  function handleCode(i: number, v: string) {
    if (!/^\d?$/.test(v)) return;
    const n = [...code]; n[i] = v; setCode(n);
    if (v && i < 5) document.querySelector<HTMLInputElement>(`[data-cidx="${i + 1}"]`)?.focus();
  }
  function pasteCode(e: React.ClipboardEvent) {
    const p = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (p.length === 6) { setCode(p.split('')); document.querySelector<HTMLInputElement>('[data-cidx="5"]')?.focus(); }
  }
  function keyCode(i: number, e: React.KeyboardEvent) {
    if (e.key === 'Backspace' && !code[i] && i > 0) document.querySelector<HTMLInputElement>(`[data-cidx="${i - 1}"]`)?.focus();
  }
  async function submitCode(e: FormEvent) {
    e.preventDefault();
    const full = code.join('');
    if (full.length !== 6) { setError('6 chiffres requis.'); return; }
    setError(''); setBusy(true);
    const res = await verifyCode(email, full);
    setBusy(false);
    if (res.ok) navigate('/home', { replace: true });
    else setError(res.error || 'Code invalide.');
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'white', padding: '0 16px' }}>
      <div style={{ width: '100%', maxWidth: '380px' }}>
        {step === 'form' ? (
          <>
            <Link to="/home" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '14px', color: 'var(--gray-500)', marginBottom: '32px', textDecoration: 'none' }}><ArrowLeft size={15} /> Retour</Link>
            <h1 style={{ fontSize: '26px', fontWeight: 700, color: 'var(--gray-900)', margin: '0 0 4px', letterSpacing: '-0.02em' }}>Créer un compte</h1>
            <p style={{ fontSize: '14px', color: 'var(--gray-500)', margin: '0 0 32px' }}>Sauvegardez vos traductions et débloquez plus de fonctionnalités.</p>
            <form onSubmit={handleRegister} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {error && <div style={{ padding: '12px', borderRadius: '10px', background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca', fontSize: '14px' }}>{error}</div>}
              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--gray-700)', marginBottom: '6px' }}>Nom <span style={{ color: 'var(--gray-400)', fontWeight: 400 }}>(optionnel)</span></label>
                <div style={{ position: 'relative' }}>
                  <User size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--gray-400)' }} />
                  <input type="text" value={name} autoFocus onChange={e => setName(e.target.value)} placeholder="Jean Dupont" style={inputBase}
                    onFocus={e => { e.target.style.borderColor = 'var(--blue)'; e.target.style.background = 'white'; }}
                    onBlur={e => { e.target.style.borderColor = 'var(--gray-200)'; e.target.style.background = 'var(--gray-50)'; }} />
                </div>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--gray-700)', marginBottom: '6px' }}>Email</label>
                <div style={{ position: 'relative' }}>
                  <Mail size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--gray-400)' }} />
                  <input type="email" required value={email} onChange={e => setEmail(e.target.value)} placeholder="vous@exemple.com" style={inputBase}
                    onFocus={e => { e.target.style.borderColor = 'var(--blue)'; e.target.style.background = 'white'; }}
                    onBlur={e => { e.target.style.borderColor = 'var(--gray-200)'; e.target.style.background = 'var(--gray-50)'; }} />
                </div>
              </div>
              <button type="submit" disabled={busy} style={{ ...btnPrimary, opacity: busy ? 0.6 : 1 }}>
                {busy ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <ArrowRight size={16} />}
                Recevoir le code
              </button>
              <p style={{ textAlign: 'center', fontSize: '14px', color: 'var(--gray-500)', margin: 0 }}>
                Déjà un compte ?{' '}<Link to="/login" style={{ color: 'var(--blue)', fontWeight: 600, textDecoration: 'none' }}>Se connecter</Link>
              </p>
            </form>
          </>
        ) : (
          <>
            <button onClick={() => setStep('form')} style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '14px', color: 'var(--gray-500)', marginBottom: '32px', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit', padding: 0 }}><ArrowLeft size={15} /> Modifier</button>
            <div style={{ textAlign: 'center', marginBottom: '32px' }}>
              <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '48px', height: '48px', borderRadius: '12px', background: 'var(--blue)', color: 'white', marginBottom: '16px' }}><Mail size={22} /></div>
              <h1 style={{ fontSize: '26px', fontWeight: 700, color: 'var(--gray-900)', margin: '0 0 8px', letterSpacing: '-0.02em' }}>Vérifiez votre email</h1>
              <p style={{ fontSize: '14px', color: 'var(--gray-500)', margin: 0, lineHeight: 1.6 }}>Code envoyé à <span style={{ fontWeight: 600, color: 'var(--gray-700)' }}>{email}</span></p>
            </div>
            <form onSubmit={submitCode} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {error && <div style={{ padding: '12px', borderRadius: '10px', background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca', fontSize: '14px' }}>{error}</div>}
              <div style={{ display: 'flex', justifyContent: 'center', gap: '8px' }} onPaste={pasteCode}>
                {code.map((d, i) => (
                  <input key={i} data-cidx={i} type="text" inputMode="numeric" maxLength={1} value={d}
                    onChange={e => handleCode(i, e.target.value)} onKeyDown={e => keyCode(i, e)}
                    onFocus={e => { e.target.style.borderColor = 'var(--blue)'; e.target.style.background = 'white'; }}
                    onBlur={e => { e.target.style.borderColor = 'var(--gray-200)'; e.target.style.background = 'var(--gray-50)'; }}
                    style={digitBase} autoFocus={i === 0} />
                ))}
              </div>
              <button type="submit" disabled={busy} style={{ ...btnPrimary, opacity: busy ? 0.6 : 1 }}>
                {busy ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <ArrowRight size={16} />}
                Créer mon compte
              </button>
              <div style={{ textAlign: 'center' }}>
                <button type="button" onClick={async () => { await resendVerification(email); setResent(true); setTimeout(() => setResent(false), 3000); }}
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
