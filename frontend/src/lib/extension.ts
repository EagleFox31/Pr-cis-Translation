// Extension navigateur Précis : détection du navigateur et de l'installation.
// L'extension répond au message `precis-ping` (externally_connectable, limité
// à l'origine du site). Tout échec se lit « non installée », sans erreur.

export type Navigateur = 'edge' | 'chrome' | 'autre';

const env = import.meta.env;

export const EXTENSION_ID = {
  chrome: env.VITE_EXTENSION_ID_CHROME ?? '',
  edge: env.VITE_EXTENSION_ID_EDGE ?? '',
};

export const EXTENSION_URL = {
  chrome: env.VITE_EXTENSION_URL_CHROME ?? '',
  edge: env.VITE_EXTENSION_URL_EDGE ?? '',
};

/** ZIP d'installation manuelle, proposé tant qu'aucune boutique n'est renseignée. */
export const EXTENSION_ZIP = {
  url: env.VITE_EXTENSION_ZIP_URL || '/extension/precis-extension.zip',
  version: __EXTENSION_VERSION__,
};

/** Vrai si `installee` est strictement plus ancienne que `disponible` (versions x.y.z). */
export function versionPlusAncienne(installee: string, disponible: string): boolean {
  const a = installee.split('.').map((n) => parseInt(n, 10) || 0);
  const b = disponible.split('.').map((n) => parseInt(n, 10) || 0);
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    const d = (a[i] ?? 0) - (b[i] ?? 0);
    if (d !== 0) return d < 0;
  }
  return false;
}

const DELAI_MS = 1500; // marge pour un fil principal chargé au premier rendu

export function detecterNavigateur(): Navigateur {
  if (typeof navigator === 'undefined') return 'autre';
  const ua = navigator.userAgent || '';
  if (ua.includes('Edg/')) return 'edge';
  if (/Chrome\/|Chromium\//.test(ua)) return 'chrome';
  return 'autre';
}

export function estMobile(): boolean {
  if (typeof navigator === 'undefined') return false;
  const mobile = (navigator as Navigator & { userAgentData?: { mobile?: boolean } }).userAgentData?.mobile;
  if (typeof mobile === 'boolean') return mobile;
  return /Android|iPhone|iPad|Mobile/i.test(navigator.userAgent || '');
}

export type EtatExtension = { installe: boolean; version?: string };

type ChromeRuntime = {
  lastError?: unknown;
  sendMessage?: (id: string, message: unknown, cb: (reponse?: unknown) => void) => void;
};

function ping(id: string): Promise<EtatExtension> {
  return new Promise((resolve) => {
    const runtime = (globalThis as { chrome?: { runtime?: ChromeRuntime } }).chrome?.runtime;
    if (!id || !runtime?.sendMessage) {
      resolve({ installe: false });
      return;
    }
    const minuteur = setTimeout(() => resolve({ installe: false }), DELAI_MS);
    try {
      runtime.sendMessage(id, { type: 'precis-ping' }, (reponse) => {
        clearTimeout(minuteur);
        // Lire lastError évite l'alerte « Unchecked runtime.lastError ».
        if (runtime.lastError) {
          resolve({ installe: false });
          return;
        }
        const r = reponse as { installe?: boolean; version?: string } | undefined;
        resolve(r?.installe === true ? { installe: true, version: r.version } : { installe: false });
      });
    } catch {
      clearTimeout(minuteur);
      resolve({ installe: false });
    }
  });
}

/** Interroge l'identifiant du navigateur détecté (les deux si inconnu). */
export async function extensionInstallee(): Promise<EtatExtension> {
  const nav = detecterNavigateur();
  const ids = nav === 'edge' ? [EXTENSION_ID.edge]
    : nav === 'chrome' ? [EXTENSION_ID.chrome]
    : [EXTENSION_ID.chrome, EXTENSION_ID.edge];
  const reponses = await Promise.all(ids.map(ping));
  return reponses.find((r) => r.installe) ?? { installe: false };
}
