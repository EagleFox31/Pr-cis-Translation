/**
 * Client HTTP pour l'API backend — gestion automatique du JWT + refresh.
 */
// Vide = même origine, le proxy Vite redirige /api vers le backend
const API_BASE = import.meta.env.VITE_API_BASE || '';

let _accessToken: string | null = null;
let _refreshToken: string | null = null;
let _onTokensRefreshed: ((access: string, refresh: string) => void) | null = null;
let _onForceLogout: (() => void) | null = null;

export function setTokens(access: string | null, refresh: string | null) {
  _accessToken = access;
  _refreshToken = refresh;
}

export function onTokensRefreshed(fn: (access: string, refresh: string) => void) {
  _onTokensRefreshed = fn;
}

export function onForceLogout(fn: () => void) {
  _onForceLogout = fn;
}

async function refreshAccessToken(): Promise<string | null> {
  if (!_refreshToken) return null;
  try {
    const res = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: _refreshToken }),
    });
    if (!res.ok) {
      _onForceLogout?.();
      return null;
    }
    const data = await res.json();
    _accessToken = data.access_token;
    _refreshToken = data.refresh_token;
    _onTokensRefreshed?.(data.access_token, data.refresh_token);
    return data.access_token;
  } catch {
    return null;
  }
}

async function request(
  method: string,
  path: string,
  body?: unknown,
): Promise<{ ok: boolean; status: number; data: unknown }> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`;
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (_accessToken) headers['Authorization'] = `Bearer ${_accessToken}`;

  let res = await fetch(url, { method, headers, body: body ? JSON.stringify(body) : undefined });

  if (res.status === 401 && _refreshToken) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      headers['Authorization'] = `Bearer ${newToken}`;
      res = await fetch(url, { method, headers, body: body ? JSON.stringify(body) : undefined });
    }
  }

  let data: unknown = null;
  try { data = await res.json(); } catch { /* pas de JSON */ }

  return { ok: res.ok, status: res.status, data };
}

const api = {
  get: (path: string) => request('GET', path),
  post: (path: string, body?: unknown) => request('POST', path, body),
  delete: (path: string) => request('DELETE', path),
};

export default api;
