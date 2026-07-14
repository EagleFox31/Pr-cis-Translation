import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Eye, EyeOff, Mail, Lock, LogIn, Loader2, ArrowLeft } from 'lucide-react';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const verified = params.get('verified') === '1';

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setBusy(true);
    const res = await login(email, password);
    setBusy(false);
    if (res.ok) navigate('/home', { replace: true });
    else setError(res.error || 'Erreur de connexion.');
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-white px-4">
      <div className="w-full max-w-sm">
        {/* Retour */}
        <Link to="/home"
          className="inline-flex items-center gap-1.5 text-sm mb-8"
          style={{ color: 'var(--gray-500)' }}
        >
          <ArrowLeft size={15} /> Retour
        </Link>

        <h1 className="text-2xl font-bold tracking-tight mb-1" style={{ color: 'var(--gray-900)' }}>
          Connexion
        </h1>
        <p className="text-sm mb-8" style={{ color: 'var(--gray-500)' }}>
          Accédez à votre espace de traduction.
        </p>

        {verified && (
          <div className="mb-5 p-3 rounded-lg text-sm font-medium"
            style={{ background: '#ecfdf5', color: '#065f46', border: '1px solid #a7f3d0' }}>
            ✅ Email vérifié — connectez-vous.
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="p-3 rounded-lg text-sm"
              style={{ background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca' }}>
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--gray-700)' }}>Email</label>
            <div className="relative">
              <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--gray-400)' }} />
              <input type="email" required autoFocus value={email}
                onChange={e => setEmail(e.target.value)}
                className="w-full pl-10 pr-3 py-2.5 rounded-lg text-sm outline-none transition-colors"
                style={{ border: '1.5px solid var(--gray-200)', background: 'var(--gray-50)' }}
                placeholder="vous@exemple.com"
                onFocus={e => { e.target.style.borderColor = 'var(--blue)'; e.target.style.background = 'white'; }}
                onBlur={e => { e.target.style.borderColor = 'var(--gray-200)'; e.target.style.background = 'var(--gray-50)'; }}
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
                placeholder="••••••••"
                onFocus={e => { e.target.style.borderColor = 'var(--blue)'; e.target.style.background = 'white'; }}
                onBlur={e => { e.target.style.borderColor = 'var(--gray-200)'; e.target.style.background = 'var(--gray-50)'; }}
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
            {busy ? <Loader2 size={16} className="animate-spin" /> : <LogIn size={16} />}
            Se connecter
          </button>

          <div className="relative my-5">
            <div className="absolute inset-0 flex items-center"><div className="w-full border-t" style={{ borderColor: 'var(--gray-200)' }} /></div>
            <div className="relative flex justify-center text-xs"><span className="bg-white px-2" style={{ color: 'var(--gray-400)' }}>ou</span></div>
          </div>

          <div id="google-signin-button" className="flex justify-center" />

          <p className="text-center text-sm" style={{ color: 'var(--gray-500)' }}>
            Pas encore de compte ?{' '}
            <Link to="/register" style={{ color: 'var(--blue)', fontWeight: 600 }}>S'inscrire</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
