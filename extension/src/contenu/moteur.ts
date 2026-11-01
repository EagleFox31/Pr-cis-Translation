import { versBackground } from "../pont.ts";

// Types minimaux des API de traduction intégrées au navigateur (Chrome 138+).
interface TraducteurNavigateur {
  translate(texte: string): Promise<string>;
}
interface OptionsTraducteur {
  sourceLanguage: string;
  targetLanguage: string;
}
interface TraducteurStatique {
  availability(options: OptionsTraducteur): Promise<string>;
  create(options: OptionsTraducteur): Promise<TraducteurNavigateur>;
}
interface DetecteurNavigateur {
  detect(texte: string): Promise<{ detectedLanguage: string; confidence: number }[]>;
}
interface DetecteurStatique {
  create(): Promise<DetecteurNavigateur>;
}

export type Progres = (fait: number, total: number) => void;

export interface Moteur {
  traduire(textes: string[], progres?: Progres): Promise<string[]>;
}

export type ResultatMoteur =
  | { ok: true; moteur: Moteur }
  | { ok: false; raison: "navigateur" | "meme_langue" };

// Erreur d'un appel Précis, avec le code renvoyé par le background.
export class ErreurPrecis extends Error {
  readonly code: string;
  constructor(code: string) {
    super(code);
    this.code = code;
  }
}

const principale = (code: string) => code.toLowerCase().split("-")[0];

function moteurPrecis(langue: string): Moteur {
  return {
    async traduire(textes) {
      let rep;
      try {
        rep = await versBackground({ type: "segments", textes, langue });
      } catch {
        throw new ErreurPrecis("indisponible");
      }
      if (!rep) throw new ErreurPrecis("indisponible");
      if (!rep.ok) throw new ErreurPrecis(rep.erreur);
      return rep.traductions;
    },
  };
}

export async function creerMoteur(
  langue: string,
  qualitePrecis: boolean,
  echantillon: string,
): Promise<ResultatMoteur> {
  if (qualitePrecis) return { ok: true, moteur: moteurPrecis(langue) };

  const api = self as unknown as { Translator?: TraducteurStatique; LanguageDetector?: DetecteurStatique };
  if (!api.Translator || !api.LanguageDetector) return { ok: false, raison: "navigateur" };

  try {
    const detecteur = await api.LanguageDetector.create();
    const source = (await detecteur.detect(echantillon))[0]?.detectedLanguage;
    if (!source || source === "und") return { ok: false, raison: "navigateur" };
    if (principale(source) === principale(langue)) return { ok: false, raison: "meme_langue" };

    const options = { sourceLanguage: source, targetLanguage: langue };
    if ((await api.Translator.availability(options)) === "unavailable") {
      return { ok: false, raison: "navigateur" };
    }
    const traducteur = await api.Translator.create(options);
    return {
      ok: true,
      moteur: {
        async traduire(textes, progres) {
          const sortie: string[] = [];
          for (const texte of textes) {
            try {
              sortie.push(await traducteur.translate(texte));
            } catch {
              sortie.push(texte);
            }
            progres?.(sortie.length, textes.length);
          }
          return sortie;
        },
      },
    };
  } catch {
    return { ok: false, raison: "navigateur" };
  }
}
