// Onglet traduit : la langue choisie suit l'onglet quand un cadre ou la page change de document
// (cours SCORM dont chaque diapo est une nouvelle page), tant qu'on reste sur la même origine.
export interface Suivi {
  langue: string;
  origine: string;
  /** Onglet où l'original a été demandé sur un site « toujours traduire » : le suivi ne traduit plus. */
  arret?: boolean;
}

/** Langues proposées par le popup. */
export const LANGUES = ["fr", "en", "es", "de", "it", "pt", "ar"];

/** Langue du navigateur si elle est proposée, sinon le français. */
export function langueParDefaut(ui: string, disponibles: string[]): string {
  const code = ui.split("-")[0].toLowerCase();
  return disponibles.includes(code) ? code : "fr";
}

/** Règle d'un site, gardée en local : traduire d'office, ou ne rien proposer. */
export type RegleSite = { mode: "traduire"; langue: string } | { mode: "original" };

export const cleSite = (origine: string): string => `site:${origine}`;

export async function lireRegle(origine: string): Promise<RegleSite | null> {
  const cle = cleSite(origine);
  const stock = await chrome.storage.local.get(cle);
  return (stock[cle] as RegleSite | undefined) ?? null;
}

export async function ecrireRegle(origine: string, regle: RegleSite | null): Promise<void> {
  const cle = cleSite(origine);
  if (regle) await chrome.storage.local.set({ [cle]: regle });
  else await chrome.storage.local.remove(cle);
}

/** Que faire d'un nouveau document : traduire, proposer, ou rien. Suivi de l'onglet, puis règle, puis proposition. */
export function decision(
  suivi: Suivi | null,
  regle: RegleSite | null,
  proposer: boolean,
  cadrePrincipal: boolean,
): { langue: string } | { proposer: true } | null {
  if (suivi) return suivi.arret ? null : { langue: suivi.langue };
  if (regle) return regle.mode === "traduire" ? { langue: regle.langue } : null;
  return proposer && cadrePrincipal ? { proposer: true } : null;
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

/** Vrai si la nouvelle adresse de l'onglet garde la traduction ; faux : on oublie l'onglet.
 *  Une adresse sans origine web (about:blank d'une fenêtre qui s'ouvre) ne le fait pas oublier. */
export function resteSuivi(suivi: Suivi, url: string | undefined): boolean {
  const origine = origineDe(url);
  return origine === null || origine === suivi.origine;
}

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
