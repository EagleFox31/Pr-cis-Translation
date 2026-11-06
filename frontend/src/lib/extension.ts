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
