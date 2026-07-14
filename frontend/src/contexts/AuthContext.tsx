import {
  createContext, useContext, useState, useEffect, useCallback,
  type ReactNode,
} from 'react';
import api, { setTokens, onTokensRefreshed, onForceLogout } from '../services/api';

export interface AuthUser {
  id: string;
  email: string;
  name: string | null;
  email_verified: boolean;
  avatar_url: string | null;
  plan: string;
  storage_used: number;
  storage_limit: number;
}

interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<{ ok: boolean; error?: string }>;
  register: (email: string, password: string, name?: string) => Promise<{ ok: boolean; error?: string }>;
  verifyCode: (email: string, code: string) => Promise<{ ok: boolean; error?: string }>;
  resendVerification: (email: string) => Promise<void>;
  googleAuth: (credential: string) => Promise<{ ok: boolean; error?: string }>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

const TOKENS_KEY = 'precis_tokens';

function loadTokens(): { access: string; refresh: string } | null {
  try {
    const raw = localStorage.getItem(TOKENS_KEY);
    if (!raw) return null;
    const { access_token, refresh_token } = JSON.parse(raw);
    if (access_token && refresh_token) return { access: access_token, refresh: refresh_token };
  } catch { /* ignoré */ }
  return null;
}

function saveTokens(access: string, refresh: string) {
  localStorage.setItem(TOKENS_KEY, JSON.stringify({ access_token: access, refresh_token: refresh }));
}

function clearTokens() {
  localStorage.removeItem(TOKENS_KEY);
  setTokens(null, null);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  // Restaurer la session au montage
  useEffect(() => {
    onTokensRefreshed((access, refresh) => saveTokens(access, refresh));
    onForceLogout(() => { clearTokens(); setUser(null); });

    (async () => {
      const tokens = loadTokens();
      if (!tokens) { setLoading(false); return; }
      setTokens(tokens.access, tokens.refresh);
      const res = await api.get('/api/auth/me');
      if (res.ok) {
        setUser(res.data as AuthUser);
      } else {
        clearTokens();
      }
      setLoading(false);
    })();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.post('/api/auth/login', { email, password });
    if (!res.ok) return { ok: false, error: (res.data as any)?.detail || 'Email ou mot de passe incorrect.' };
    const d = res.data as any;
    saveTokens(d.access_token, d.refresh_token);
    setTokens(d.access_token, d.refresh_token);
    setUser(d.user);
    return { ok: true };
  }, []);

  const register = useCallback(async (email: string, password: string, name?: string) => {
    const res = await api.post('/api/auth/register', { email, password, name });
    if (!res.ok) return { ok: false, error: (res.data as any)?.detail || "Erreur lors de l'inscription." };
    return { ok: true };
  }, []);

  const verifyCode = useCallback(async (email: string, code: string) => {
    const res = await api.post('/api/auth/verify-email', { email, code });
    if (!res.ok) return { ok: false, error: (res.data as any)?.detail || 'Code invalide ou expiré.' };
    const d = res.data as any;
    saveTokens(d.access_token, d.refresh_token);
    setTokens(d.access_token, d.refresh_token);
    setUser(d.user);
    return { ok: true };
  }, []);

  const resendVerification = useCallback(async (email: string) => {
    await api.post('/api/auth/resend-verification', { email });
  }, []);

  const googleAuth = useCallback(async (credential: string) => {
    const res = await api.post('/api/auth/google', { credential });
    if (!res.ok) return { ok: false, error: (res.data as any)?.detail || 'Authentification Google échouée.' };
    const d = res.data as any;
    saveTokens(d.access_token, d.refresh_token);
    setTokens(d.access_token, d.refresh_token);
    setUser(d.user);
    return { ok: true };
  }, []);

  const logout = useCallback(async () => {
    try { await api.post('/api/auth/logout'); } catch { /* ignoré */ }
    clearTokens();
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    const res = await api.get('/api/auth/me');
    if (res.ok) setUser(res.data as AuthUser);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, verifyCode, resendVerification, googleAuth, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
