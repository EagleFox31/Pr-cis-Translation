// Onglet traduit : la langue choisie suit l'onglet quand un cadre ou la page change de document
// (cours SCORM dont chaque diapo est une nouvelle page), tant qu'on reste sur la même origine.
export interface Suivi {
  langue: string;
  origine: string;
}

export const cleSuivi = (tabId: number): string => `suivi:${tabId}`;

export function origineDe(url: string | undefined): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    return u.protocol === "http:" || u.protocol === "https:" ? u.origin : null;
  } catch {
    return null;
  }
}

/** Vrai si la nouvelle adresse de l'onglet garde la traduction ; faux : on oublie l'onglet. */
export const resteSuivi = (suivi: Suivi, url: string | undefined): boolean => origineDe(url) === suivi.origine;

export async function lireSuivi(tabId: number): Promise<Suivi | null> {
  const cle = cleSuivi(tabId);
  const stock = await chrome.storage.session.get(cle);
  return (stock[cle] as Suivi | undefined) ?? null;
}

export async function ecrireSuivi(tabId: number, suivi: Suivi | null): Promise<void> {
  const cle = cleSuivi(tabId);
  if (suivi) await chrome.storage.session.set({ [cle]: suivi });
  else await chrome.storage.session.remove(cle);
}
