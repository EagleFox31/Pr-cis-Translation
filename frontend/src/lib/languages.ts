/**
 * Catalogue des langues cibles.
 *
 * `code` est le code réellement ENVOYÉ à l'API. On ne propose plus de variantes
 * régionales (en-US / en-GB / fr-CA …) : le client les réduisait de toute façon
 * à leur base (`'en-US'.split('-')[0]`), donc deux variantes d'une même langue
 * produisaient une requête identique — un choix sans effet.
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
  code: string;
  label: string;
  script: Script;
}

export const LANGUAGES: Language[] = [
  { code: 'en', label: 'English', script: 'latin' },
  { code: 'fr', label: 'Français', script: 'latin' },
  { code: 'es', label: 'Español', script: 'latin' },
  { code: 'de', label: 'Deutsch', script: 'latin' },
  { code: 'it', label: 'Italiano', script: 'latin' },
  { code: 'pt', label: 'Português', script: 'latin' },
  { code: 'nl', label: 'Nederlands', script: 'latin' },
  { code: 'pl', label: 'Polski', script: 'latin' },
  { code: 'ro', label: 'Română', script: 'latin' },
  { code: 'cs', label: 'Čeština', script: 'latin' },
  { code: 'hu', label: 'Magyar', script: 'latin' },
  { code: 'tr', label: 'Türkçe', script: 'latin' },
  { code: 'sv', label: 'Svenska', script: 'latin' },
  { code: 'da', label: 'Dansk', script: 'latin' },
  { code: 'nb', label: 'Norsk bokmål', script: 'latin' },
  { code: 'fi', label: 'Suomi', script: 'latin' },
  { code: 'ru', label: 'Русский', script: 'cyrillic' },
  { code: 'uk', label: 'Українська', script: 'cyrillic' },
  { code: 'el', label: 'Ελληνικά', script: 'greek' },
  { code: 'zh', label: '中文', script: 'cjk' },
  { code: 'ja', label: '日本語', script: 'cjk' },
  { code: 'ko', label: '한국어', script: 'cjk' },
  { code: 'ar', label: 'العربية', script: 'arabic' },
];

/** Écritures que le rendu PDF sait produire (polices de repli vérifiées). */
const PDF_SCRIPTS: Script[] = ['latin', 'cyrillic'];

/** La langue est-elle rendable dans le format demandé ? */
export function isLangAvailable(lang: Language, ext: string): boolean {
  if (ext !== 'pdf') return true;          // DOCX/TXT : la police vient du lecteur
  return PDF_SCRIPTS.includes(lang.script);
}

export function findLang(code: string): Language | undefined {
  return LANGUAGES.find((l) => l.code === code);
}
