import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Eye, EyeOff, Mail, Lock, User, UserPlus, Loader2, ArrowLeft } from 'lucide-react';

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
    if (password.length < 8) {
      setError('Le mot de passe doit contenir au moins 8 caractères.');
      return;
    }
    setBusy(true);
    const res = await register(email, password, name || undefined);
    setBusy(false);
    if (res.ok) {
      navigate(`/verify-email?email=${encodeURIComponent(email)}`, { replace: true });
    } else {
      setError(res.error || "Erreur lors de l'inscription.");
    }
  }

  const inputClass = "w-full pl-10 pr-3 py-2.5 rounded-lg text-sm outline-none transition-colors";
  const inputStyle = (e: React.FocusEvent<HTMLInputElement>) => {
    e.target.style.borderColor = 'var(--blue)'; e.target.style.background = 'white';
  };
  const inputBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    e.target.style.borderColor = 'var(--gray-200)'; e.target.style.background = 'var(--gray-50)';
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-white px-4">
      <div className="w-full max-w-sm">
        <Link to="/home"
          className="inline-flex items-center gap-1.5 text-sm mb-8"
          style={{ color: 'var(--gray-500)' }}
        >
          <ArrowLeft size={15} /> Retour
        </Link>

        <h1 className="text-2xl font-bold tracking-tight mb-1" style={{ color: 'var(--gray-900)' }}>
          Créer un compte
        </h1>
        <p className="text-sm mb-8" style={{ color: 'var(--gray-500)' }}>
          Sauvegardez vos traductions et débloquez plus de fonctionnalités.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="p-3 rounded-lg text-sm"
              style={{ background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca' }}>
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--gray-700)' }}>
              Nom <span style={{ color: 'var(--gray-400)', fontWeight: 400 }}>(optionnel)</span>
            </label>
            <div className="relative">
              <User size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--gray-400)' }} />
              <input type="text" value={name} autoFocus onChange={e => setName(e.target.value)}
                className={inputClass} style={{ border: '1.5px solid var(--gray-200)', background: 'var(--gray-50)' }}
                placeholder="Jean Dupont"
                onFocus={inputStyle} onBlur={inputBlur}
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--gray-700)' }}>Email</label>
            <div className="relative">
              <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--gray-400)' }} />
              <input type="email" required value={email} onChange={e => setEmail(e.target.value)}
                className={inputClass} style={{ border: '1.5px solid var(--gray-200)', background: 'var(--gray-50)' }}
                placeholder="vous@exemple.com"
                onFocus={inputStyle} onBlur={inputBlur}
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--gray-700)' }}>Mot de passe</label>
            <div className="relative">
              <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--gray-400)' }} />
              <input type={showPw ? 'text' : 'password'} required value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full pl-10 pr-10 py-2.5 rounded-lg text-sm outline-none transition-colors"
                style={{ border: '1.5px solid var(--gray-200)', background: 'var(--gray-50)' }}
                placeholder="8 caractères minimum"
                onFocus={inputStyle} onBlur={inputBlur}
              />
              <button type="button" onClick={() => setShowPw(!showPw)}
                className="absolute right-3 top-1/2 -translate-y-1/2"
                style={{ color: 'var(--gray-400)' }}>
                {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <button type="submit" disabled={busy}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-semibold transition-all"
            style={{ background: 'var(--blue)', color: 'white', opacity: busy ? 0.6 : 1 }}>
            {busy ? <Loader2 size={16} className="animate-spin" /> : <UserPlus size={16} />}
            Créer mon compte
          </button>

          <p className="text-center text-sm" style={{ color: 'var(--gray-500)' }}>
            Déjà un compte ?{' '}
            <Link to="/login" style={{ color: 'var(--blue)', fontWeight: 600 }}>Se connecter</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
