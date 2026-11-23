/** Keep the beta application journey across sign-in, without external redirects. */
const CHALLENGE = /^[A-Za-z0-9_-]{43}$/;
const STATE = /^[A-Za-z0-9_-]{16,128}$/;

/** Lit `challenge` et `state` de la page d'autorisation de l'extension ;
 *  null si l'un des deux n'a pas exactement le format attendu. */
export function extensionAuthParams(params: URLSearchParams): { challenge: string; state: string } | null {
  const challenge = params.get('challenge') ?? '';
  const state = params.get('state') ?? '';
  return CHALLENGE.test(challenge) && STATE.test(state) ? { challenge, state } : null;
}

/** Page d'autorisation de l'extension, reconstruite depuis des valeurs validées. */
export function extensionAuthPath(challenge: string, state: string): string {
  return `/extension/autoriser?challenge=${challenge}&state=${state}`;
}

/** `next` accepté : /beta, ou la page d'autorisation de l'extension (chemin
 *  fixe, paramètres validés). Tout le reste retombe sur /home. */
export function authReturnTo(params: URLSearchParams): string {
  const next = params.get('next');
  if (next === '/beta') return '/beta';
  if (next && next.startsWith('/extension/autoriser?')) {
    const found = extensionAuthParams(new URLSearchParams(next.slice(next.indexOf('?') + 1)));
    if (found) return extensionAuthPath(found.challenge, found.state);
  }
  return '/home';
}

export function authPageLink(path: '/login' | '/register', params: URLSearchParams): string {
  const to = authReturnTo(params);
  return to === '/home' ? path : `${path}?next=${encodeURIComponent(to)}`;
}
