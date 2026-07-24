/**
 * Client HTTP pour l'API backend — gestion automatique du JWT + refresh.
 */
import i18n from '../i18n';

// Vide = même origine, le proxy Vite redirige /api vers le backend
const API_BASE = import.meta.env.VITE_API_BASE || '';

/**
 * La langue de l'INTERFACE, annoncée à chaque appel.
 *
 * Le backend s'en sert pour écrire ses e-mails : un code de connexion doit
 * arriver dans la langue où l'utilisateur vient de cliquer, et non dans celle
 * de son système d'exploitation. Quelqu'un dont Windows est en anglais mais qui
 * a mis Précis en français attend un e-mail en français.
 *
 * Repli sur `fr` si i18n n'est pas encore initialisé — c'est la langue par
 * défaut de l'interface, donc le repli ne ment jamais.
 */
function uiLanguage(): string {
  return i18n?.language || 'fr';
}

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

/**
 * En-tête d'authentification pour les appels qui NE passent PAS par `request()`
 * — upload multipart, téléchargement de blob, EventSource.
 *
 * À utiliser plutôt que de relire `localStorage` : après un refresh, le token
 * en mémoire est le bon et celui du storage peut être en retard d'un tour.
 * Renvoie `{}` pour un visiteur, ce qui laisse l'appel anonyme.
 */
export function authHeader(): Record<string, string> {
  return _accessToken ? { Authorization: `Bearer ${_accessToken}` } : {};
}

/** Y a-t-il une session ? (sans exposer le token lui-même) */
export function hasSession(): boolean {
  return _accessToken !== null;
}

/**
 * Le token d'accès brut — UNIQUEMENT pour EventSource, qui ne sait pas porter
 * de header. Le backend l'accepte alors en query (`?token=`) et ne journalise
 * jamais la query. Pour tout appel `fetch`, passer par `authHeader()`.
 */
export function accessToken(): string | null {
  return _accessToken;
}

/**
 * `fetch` authentifié pour les réponses NON-JSON (blob, flux). Rejoue l'appel
 * une fois après refresh sur 401, comme `request()` — sans quoi un token expiré
 * ferait échouer un téléchargement alors que la session est valide.
 */
export async function authFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`;
  const send = () => fetch(url, {
    ...init,
    headers: {
      'Accept-Language': uiLanguage(),
      ...(init.headers as Record<string, string> | undefined),
      ...authHeader(),
    },
  });
  let res = await send();
  if (res.status === 401 && _refreshToken) {
    const t = await refreshAccessToken();
    if (t) res = await send();
  }
  return res;
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
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Accept-Language': uiLanguage(),
  };
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
