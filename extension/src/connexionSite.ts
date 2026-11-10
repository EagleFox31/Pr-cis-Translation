// Connexion de l'extension par le site : code à usage unique + PKCE (S256).
// Le verifier ne quitte jamais l'extension ; le site ne reçoit que son empreinte (challenge).

function base64url(octets: Uint8Array): string {
  let binaire = "";
  for (const o of octets) binaire += String.fromCharCode(o);
  return btoa(binaire).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** 32 octets aléatoires en base64url sans remplissage : 43 caractères. */
export function genererVerifier(): string {
  return base64url(crypto.getRandomValues(new Uint8Array(32)));
}

/** Empreinte SHA-256 du verifier, en base64url sans remplissage (méthode S256). */
export async function challengeDe(verifier: string): Promise<string> {
  const empreinte = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  return base64url(new Uint8Array(empreinte));
}

/** Valeur aléatoire liée à l'onglet ouvert : le retour du site doit la reporter à l'identique. */
export function genererState(): string {
  return base64url(crypto.getRandomValues(new Uint8Array(16)));
}

/** Page du site qui demande l'accord de l'utilisateur. */
export function urlAutorisation(site: string, challenge: string, state: string): string {
  const params = new URLSearchParams({ challenge, state });
  return `${site}/extension/autoriser?${params.toString()}`;
}

export interface RetourSite {
  code?: string;
  erreur?: string;
  state?: string;
}

/** Lit le retour du site (`/extension/connecte#code=…&state=…`) ; null si l'adresse n'est pas cette page. */
export function lireRetour(url: string | undefined, site: string): RetourSite | null {
  if (!url) return null;
  let adresse: URL;
  let base: URL;
  try {
    adresse = new URL(url);
    base = new URL(site);
  } catch {
    return null;
  }
  if (adresse.origin !== base.origin) return null;
  if (adresse.pathname.replace(/\/+$/, "") !== "/extension/connecte") return null;
  const params = new URLSearchParams(adresse.hash.replace(/^#/, ""));
  const retour: RetourSite = {};
  const code = params.get("code");
  const erreur = params.get("erreur");
  const state = params.get("state");
  if (code) retour.code = code;
  if (erreur) retour.erreur = erreur;
  if (state) retour.state = state;
  return retour;
}
