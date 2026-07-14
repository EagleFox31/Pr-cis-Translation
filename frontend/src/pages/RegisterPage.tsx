import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Eye, EyeOff, Mail, Lock, User, UserPlus, Loader2, ArrowLeft } from 'lucide-react';

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

const focusIn = (e: React.FocusEvent<HTMLInputElement>) => {
  e.target.style.borderColor = 'var(--blue)'; e.target.style.background = 'white';
};
const focusOut = (e: React.FocusEvent<HTMLInputElement>) => {
  e.target.style.borderColor = 'var(--gray-200)'; e.target.style.background = 'var(--gray-50)';
};

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    if (password.length < 8) { setError('Le mot de passe doit contenir au moins 8 caractères.'); return; }
    setBusy(true);
    const res = await register(email, password, name || undefined);
    setBusy(false);
    if (res.ok) navigate(`/verify-email?email=${encodeURIComponent(email)}`, { replace: true });
    else setError(res.error || "Erreur lors de l'inscription.");
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'white', padding: '0 16px' }}>
      <div style={{ width: '100%', maxWidth: '380px' }}>
        <Link to="/home" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '14px', color: 'var(--gray-500)', marginBottom: '32px', textDecoration: 'none' }}>
          <ArrowLeft size={15} /> Retour
        </Link>

        <h1 style={{ fontSize: '26px', fontWeight: 700, color: 'var(--gray-900)', margin: '0 0 4px', letterSpacing: '-0.02em' }}>Créer un compte</h1>
        <p style={{ fontSize: '14px', color: 'var(--gray-500)', margin: '0 0 32px' }}>Sauvegardez vos traductions et débloquez plus de fonctionnalités.</p>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {error && (
            <div style={{ padding: '12px', borderRadius: '10px', background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca', fontSize: '14px' }}>{error}</div>
          )}

          <div>
            <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--gray-700)', marginBottom: '6px' }}>
              Nom <span style={{ color: 'var(--gray-400)', fontWeight: 400 }}>(optionnel)</span>
            </label>
            <div style={{ position: 'relative' }}>
              <User size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--gray-400)' }} />
              <input type="text" value={name} autoFocus onChange={e => setName(e.target.value)}
                placeholder="Jean Dupont" style={inputBase} onFocus={focusIn} onBlur={focusOut} />
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--gray-700)', marginBottom: '6px' }}>Email</label>
            <div style={{ position: 'relative' }}>
              <Mail size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--gray-400)' }} />
              <input type="email" required value={email} onChange={e => setEmail(e.target.value)}
                placeholder="vous@exemple.com" style={inputBase} onFocus={focusIn} onBlur={focusOut} />
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--gray-700)', marginBottom: '6px' }}>Mot de passe</label>
            <div style={{ position: 'relative' }}>
              <Lock size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--gray-400)' }} />
              <input type={showPw ? 'text' : 'password'} required value={password}
                onChange={e => setPassword(e.target.value)} placeholder="8 caractères minimum"
                style={{ ...inputBase, paddingRight: '38px' }} onFocus={focusIn} onBlur={focusOut} />
              <button type="button" onClick={() => setShowPw(!showPw)}
                style={{ position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--gray-400)', padding: 0 }}>
                {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <button type="submit" disabled={busy} style={{ ...btnPrimary, opacity: busy ? 0.6 : 1 }}>
            {busy ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <UserPlus size={16} />}
            Créer mon compte
          </button>

          <p style={{ textAlign: 'center', fontSize: '14px', color: 'var(--gray-500)', margin: 0 }}>
            Déjà un compte ?{' '}
            <Link to="/login" style={{ color: 'var(--blue)', fontWeight: 600, textDecoration: 'none' }}>Se connecter</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
