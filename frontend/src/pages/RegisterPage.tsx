import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Mail, User, ArrowRight, Loader2, ArrowLeft, RefreshCw, Sparkles } from 'lucide-react';

const logo = '/Logo.png';

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
const focusIn = (e: React.FocusEvent<HTMLInputElement>) => { e.target.style.borderColor = 'var(--blue)'; e.target.style.background = 'white'; };
const focusOut = (e: React.FocusEvent<HTMLInputElement>) => { e.target.style.borderColor = 'var(--gray-200)'; e.target.style.background = 'var(--gray-50)'; };

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
    e.preventDefault(); setError(''); setBusy(true);
    const res = await register(email, name || undefined); setBusy(false);
    if (res.ok) setStep('code'); else setError(res.error || 'Erreur.');
  }
  function hCode(i: number, v: string) { if (!/^\d?$/.test(v)) return; const n = [...code]; n[i] = v; setCode(n); if (v && i < 5) document.querySelector<HTMLInputElement>(`[data-ri="${i + 1}"]`)?.focus(); }
  function pCode(e: React.ClipboardEvent) { const p = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6); if (p.length === 6) { setCode(p.split('')); document.querySelector<HTMLInputElement>('[data-ri="5"]')?.focus(); } }
  function kCode(i: number, e: React.KeyboardEvent) { if (e.key === 'Backspace' && !code[i] && i > 0) document.querySelector<HTMLInputElement>(`[data-ri="${i - 1}"]`)?.focus(); }
  async function sCode(e: FormEvent) { e.preventDefault(); const f = code.join(''); if (f.length !== 6) { setError('6 chiffres requis.'); return; } setError(''); setBusy(true); const r = await verifyCode(email, f); setBusy(false); if (r.ok) navigate('/home', { replace: true }); else setError(r.error || 'Code invalide.'); }

  return (
    <div style={pageStyle}>
      <div style={cardStyle}>
        <div style={{ textAlign: 'center', marginBottom: '28px' }}>
          <img src={logo} alt="Précis" style={logoStyle} />
          <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--gray-900)', margin: '12px 0 2px', letterSpacing: '-0.02em' }}>Précis</h2>
          <p style={{ fontSize: '13px', color: 'var(--gray-400)', margin: 0 }}>Traduction intelligente</p>
        </div>

        {step === 'form' ? (
          <>
            <Link to="/home" style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', fontSize: '13px', color: 'var(--gray-400)', marginBottom: '20px', textDecoration: 'none' }}><ArrowLeft size={14} /> Accueil</Link>
            <h1 style={{ fontSize: '22px', fontWeight: 700, color: 'var(--gray-900)', margin: '0 0 4px' }}>Créer un compte</h1>
            <p style={{ fontSize: '14px', color: 'var(--gray-500)', margin: '0 0 20px', lineHeight: 1.5 }}>Sauvegardez vos traductions et débloquez plus de fonctionnalités.</p>
            <form onSubmit={handleRegister} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {error && <div style={{ padding: '10px 12px', borderRadius: '10px', background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca', fontSize: '13px' }}>{error}</div>}
              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--gray-700)', marginBottom: '5px' }}>Nom <span style={{ color: 'var(--gray-400)', fontWeight: 400 }}>(optionnel)</span></label>
                <div style={{ position: 'relative' }}>
                  <User size={15} style={{ position: 'absolute', left: '11px', top: '50%', transform: 'translateY(-50%)', color: 'var(--gray-400)' }} />
                  <input type="text" value={name} autoFocus onChange={e => setName(e.target.value)} placeholder="Jean Dupont" style={inputBase} onFocus={focusIn} onBlur={focusOut} />
                </div>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--gray-700)', marginBottom: '5px' }}>Email</label>
                <div style={{ position: 'relative' }}>
                  <Mail size={15} style={{ position: 'absolute', left: '11px', top: '50%', transform: 'translateY(-50%)', color: 'var(--gray-400)' }} />
                  <input type="email" required value={email} onChange={e => setEmail(e.target.value)} placeholder="vous@exemple.com" style={inputBase} onFocus={focusIn} onBlur={focusOut} />
                </div>
              </div>
              <button type="submit" disabled={busy} style={{ ...btnPrimary, opacity: busy ? 0.6 : 1 }}>
                {busy ? <Loader2 size={15} style={{ animation: 'spin 1s linear infinite' }} /> : <ArrowRight size={15} />}
                Recevoir le code
              </button>
              <p style={{ textAlign: 'center', fontSize: '14px', color: 'var(--gray-500)', margin: 0 }}>
                Déjà un compte ?{' '}<Link to="/login" style={{ color: 'var(--blue)', fontWeight: 600, textDecoration: 'none' }}>Se connecter</Link>
              </p>
            </form>
          </>
        ) : (
          <>
            <button onClick={() => setStep('form')} style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', fontSize: '13px', color: 'var(--gray-400)', marginBottom: '20px', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit', padding: 0 }}><ArrowLeft size={14} /> Modifier</button>
            <div style={{ textAlign: 'center', marginBottom: '24px' }}>
              <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '44px', height: '44px', borderRadius: '12px', background: 'var(--blue)', color: 'white', marginBottom: '12px' }}><Sparkles size={20} /></div>
              <h1 style={{ fontSize: '22px', fontWeight: 700, color: 'var(--gray-900)', margin: '0 0 4px' }}>Vérification</h1>
              <p style={{ fontSize: '14px', color: 'var(--gray-500)', margin: 0 }}>Code envoyé à <span style={{ fontWeight: 600, color: 'var(--gray-700)' }}>{email}</span></p>
            </div>
            <form onSubmit={sCode} style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
              {error && <div style={{ padding: '10px 12px', borderRadius: '10px', background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca', fontSize: '13px' }}>{error}</div>}
              <div style={{ display: 'flex', justifyContent: 'center', gap: '8px' }} onPaste={pCode}>
                {code.map((d, i) => (<input key={i} data-ri={i} type="text" inputMode="numeric" maxLength={1} value={d} onChange={e => hCode(i, e.target.value)} onKeyDown={e => kCode(i, e)} onFocus={focusIn} onBlur={focusOut} style={digitBase} autoFocus={i === 0} />))}
              </div>
              <button type="submit" disabled={busy} style={{ ...btnPrimary, opacity: busy ? 0.6 : 1 }}>
                {busy ? <Loader2 size={15} style={{ animation: 'spin 1s linear infinite' }} /> : <ArrowRight size={15} />}
                Créer mon compte
              </button>
              <div style={{ textAlign: 'center' }}>
                <button type="button" onClick={async () => { await resendVerification(email); setResent(true); setTimeout(() => setResent(false), 3000); }}
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
