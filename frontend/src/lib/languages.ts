/**
 * Catalogue des langues cibles.
 *
 * `code` est le code réellement ENVOYÉ à l'API, variante régionale comprise.
 * Les variantes sont légitimes — l'anglais britannique et l'américain diffèrent
 * en orthographe (colour/color), en vocabulaire et en dates — mais elles ne
 * valent que si elles atteignent le modèle : le client réduisait auparavant
 * 'en-GB' à 'en' avant l'envoi, et le backend ne savait nommer que les codes de
 * base. Les deux bouts sont désormais alignés (cf. TranslatorAI.lang_name).
 *
 * `script` conditionne la disponibilité en PDF. Le moteur v2 réutilise les
 * polices du document source et, à défaut, une police de repli latine
 * (backend/fonts : Roboto, Open Sans, PT Serif…) ou une base-14. Aucune de ces
 * polices ne contient de glyphes CJK, arabes ou grecs (couverture vérifiée
 * glyphe par glyphe) : une cible dans ces écritures rendrait un PDF vide ou
 * illisible. L'arabe demanderait en outre un reflow droite-à-gauche, absent.
 * Ces langues restent disponibles pour DOCX et TXT, où c'est le lecteur
 * (Word, éditeur de texte) qui fournit la police.
 */
export type Script = 'latin' | 'cyrillic' | 'greek' | 'cjk' | 'arabic';

export interface Language {
  /** Code envoyé à l'API ('en-GB', 'it'…). */
  code: string;
  /** Nom de la langue, dans sa propre langue. */
  name: string;
  /** Variante régionale, si la langue en propose plusieurs. */
  region?: string;
  script: Script;
}

export const LANGUAGES: Language[] = [
  { code: 'en-US', name: 'English', region: 'United States', script: 'latin' },
  { code: 'en-GB', name: 'English', region: 'United Kingdom', script: 'latin' },
  { code: 'en-CA', name: 'English', region: 'Canada', script: 'latin' },
  { code: 'en-AU', name: 'English', region: 'Australia', script: 'latin' },

  { code: 'fr-FR', name: 'Français', region: 'France', script: 'latin' },
  { code: 'fr-CA', name: 'Français', region: 'Canada', script: 'latin' },
  { code: 'fr-BE', name: 'Français', region: 'Belgique', script: 'latin' },
  { code: 'fr-CH', name: 'Français', region: 'Suisse', script: 'latin' },

  { code: 'es-ES', name: 'Español', region: 'España', script: 'latin' },
  { code: 'es-MX', name: 'Español', region: 'México', script: 'latin' },
  { code: 'es-AR', name: 'Español', region: 'Argentina', script: 'latin' },

  { code: 'de-DE', name: 'Deutsch', region: 'Deutschland', script: 'latin' },
  { code: 'de-AT', name: 'Deutsch', region: 'Österreich', script: 'latin' },
  { code: 'de-CH', name: 'Deutsch', region: 'Schweiz', script: 'latin' },

  { code: 'pt-PT', name: 'Português', region: 'Portugal', script: 'latin' },
  { code: 'pt-BR', name: 'Português', region: 'Brasil', script: 'latin' },

  { code: 'nl-NL', name: 'Nederlands', region: 'Nederland', script: 'latin' },
  { code: 'nl-BE', name: 'Nederlands', region: 'België', script: 'latin' },

  { code: 'it', name: 'Italiano', script: 'latin' },
  { code: 'pl', name: 'Polski', script: 'latin' },
  { code: 'ro', name: 'Română', script: 'latin' },
  { code: 'cs', name: 'Čeština', script: 'latin' },
  { code: 'hu', name: 'Magyar', script: 'latin' },
  { code: 'tr', name: 'Türkçe', script: 'latin' },
  { code: 'sv', name: 'Svenska', script: 'latin' },
  { code: 'da', name: 'Dansk', script: 'latin' },
  { code: 'nb', name: 'Norsk bokmål', script: 'latin' },
  { code: 'fi', name: 'Suomi', script: 'latin' },

  { code: 'ru', name: 'Русский', script: 'cyrillic' },
  { code: 'uk', name: 'Українська', script: 'cyrillic' },

  { code: 'el', name: 'Ελληνικά', script: 'greek' },

  { code: 'zh-CN', name: '中文', region: '简体', script: 'cjk' },
  { code: 'zh-TW', name: '中文', region: '繁體', script: 'cjk' },
  { code: 'ja', name: '日本語', script: 'cjk' },
  { code: 'ko', name: '한국어', script: 'cjk' },
  { code: 'ar', name: 'العربية', script: 'arabic' },
];

/** Écritures que le rendu PDF sait produire (polices de repli vérifiées). */
const PDF_SCRIPTS: Script[] = ['latin', 'cyrillic'];

/** 'en-GB' → 'en'. Sert aux affichages courts (badges, vignettes). */
export function baseCode(code: string): string {
  return code.split('-')[0];
}

/** La langue est-elle rendable dans le format demandé ? */
export function isLangAvailable(lang: Language, ext: string): boolean {
  if (ext !== 'pdf') return true;          // DOCX/TXT : la police vient du lecteur
  return PDF_SCRIPTS.includes(lang.script);
}

export function findLang(code: string): Language | undefined {
  return LANGUAGES.find((l) => l.code === code);
}

/** Libellé complet : « English (United Kingdom) ». */
export function langLabel(lang: Language): string {
  return lang.region ? `${lang.name} (${lang.region})` : lang.name;
}
