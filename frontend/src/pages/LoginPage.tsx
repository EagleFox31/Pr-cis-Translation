import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Eye, EyeOff, Mail, Lock, LogIn, Loader2 } from 'lucide-react';

export default function LoginPage() {
  const { login, googleAuth } = useAuth();
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
    <div className="min-h-screen flex items-center justify-center bg-neutral-50 px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold tracking-tight text-neutral-900">Precis</h1>
          <p className="text-sm text-neutral-500 mt-1">Connectez-vous à votre compte</p>
        </div>

        {verified && (
          <div className="mb-4 p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-700 text-center">
            ✅ Email vérifié — connectez-vous.
          </div>
        )}

        <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border border-neutral-200 p-6 space-y-4">
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
          )}

          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1">Email</label>
            <div className="relative">
              <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" />
              <input
                type="email" required autoFocus value={email}
                onChange={e => setEmail(e.target.value)}
                className="w-full pl-10 pr-3 py-2.5 border border-neutral-300 rounded-lg text-sm focus:ring-2 focus:ring-neutral-900 focus:border-neutral-900 outline-none"
                placeholder="vous@exemple.com"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1">Mot de passe</label>
            <div className="relative">
              <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" />
              <input
                type={showPw ? 'text' : 'password'} required value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full pl-10 pr-10 py-2.5 border border-neutral-300 rounded-lg text-sm focus:ring-2 focus:ring-neutral-900 focus:border-neutral-900 outline-none"
                placeholder="••••••••"
              />
              <button type="button" onClick={() => setShowPw(!showPw)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-600">
                {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <button type="submit" disabled={busy}
            className="w-full flex items-center justify-center gap-2 bg-neutral-900 text-white py-2.5 rounded-lg text-sm font-medium hover:bg-neutral-800 disabled:opacity-50 transition-colors">
            {busy ? <Loader2 size={16} className="animate-spin" /> : <LogIn size={16} />}
            Se connecter
          </button>

          {/* Google OAuth */}
          <div className="relative my-4">
            <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-neutral-200" /></div>
            <div className="relative flex justify-center text-xs"><span className="bg-white px-2 text-neutral-400">ou</span></div>
          </div>

          <div id="google-signin-button" className="flex justify-center" />

          <p className="text-center text-sm text-neutral-500">
            Pas encore de compte ?{' '}
            <Link to="/register" className="text-neutral-900 font-medium hover:underline">S'inscrire</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
