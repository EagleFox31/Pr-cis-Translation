// Langue d'une page à proposer en traduction, d'après la détection du navigateur.
export interface Detection {
  isReliable: boolean;
  languages: { language: string; percentage: number }[];
}

const LONGUEUR_MIN = 200;

/** Code de la langue de la page si elle diffère de la cible, sinon null (texte trop court, inconnue, déjà la cible). */
export function langueAProposer(detection: Detection, htmlLang: string, cible: string, longueur: number): string | null {
  if (longueur < LONGUEUR_MIN) return null;
  let langue: string | null = null;
  if (detection.isReliable) langue = detection.languages[0]?.language.split("-")[0] ?? null;
  else if (htmlLang) langue = htmlLang.split("-")[0];
  if (!langue || langue === "und" || langue === cible) return null;
  return langue;
}

/** Nom français d'une langue, ou son code si le navigateur ne le connaît pas. */
export function nomLangue(code: string): string {
  try {
    return new Intl.DisplayNames(["fr"], { type: "language" }).of(code) ?? code;
  } catch {
    return code;
  }
}
