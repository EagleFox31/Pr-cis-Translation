/** Données de la visite d'accueil : étapes, icônes et scénario des cinq scènes. */

export type CleEtape = 'traduction' | 'scans' | 'extension' | 'api' | 'visionneuse';

/** Tracés des icônes (viewBox 24, trait). */
export const IC: Record<string, string> = {
  doc: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
  layout: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/>',
  repeat: '<path d="m17 2 4 4-4 4"/><path d="M3 11v-1a4 4 0 0 1 4-4h14"/><path d="m7 22-4-4 4-4"/><path d="M21 13v1a4 4 0 0 1-4 4H3"/>',
  scan: '<path d="M3 7V5a2 2 0 0 1 2-2h2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/><path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/><path d="M7 12h10"/>',
  image: '<rect width="18" height="18" x="3" y="3" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/>',
  chart: '<path d="M3 3v18h18"/><path d="M7 16v-5"/><path d="M12 16V8"/><path d="M17 16v-3"/>',
  gift: '<rect x="3" y="8" width="18" height="4" rx="1"/><path d="M12 8v13"/><path d="M19 12v7a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-7"/>',
  globe: '<circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15 15 0 0 1 0 20 15 15 0 0 1 0-20"/>',
  zap: '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>',
  plug: '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/>',
  columns: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M12 3v18"/>',
  undo: '<path d="M9 14 4 9l5-5"/><path d="M4 9h11a5 5 0 0 1 0 10h-3"/>',
  pen: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
};

export interface EtapeDef {
  cle: CleEtape;
  /** Étape annoncée « Bientôt » (pastille dans le sur-titre). */
  soon?: boolean;
  /** Icône de chaque point ; `later` : point à venir (pointillés). */
  pts: ReadonlyArray<{ icone: string; later?: boolean }>;
}

export const ETAPES: ReadonlyArray<EtapeDef> = [
  { cle: 'traduction', pts: [{ icone: 'doc' }, { icone: 'layout' }, { icone: 'repeat' }] },
  { cle: 'scans', pts: [{ icone: 'scan' }, { icone: 'chart' }, { icone: 'image' }] },
  { cle: 'extension', pts: [{ icone: 'gift' }, { icone: 'image' }, { icone: 'globe' }] },
  { cle: 'api', soon: true, pts: [{ icone: 'zap' }, { icone: 'layout' }, { icone: 'plug' }] },
  { cle: 'visionneuse', pts: [{ icone: 'columns' }, { icone: 'undo' }, { icone: 'pen', later: true }] },
];

/**
 * Scénario : d = durée (ms) ; l = langue du texte ; li = langue des images ;
 * w = délai avant changement ; p = pastille de langue ; cur = position du curseur ;
 * clk = clic. La légende est `nouveautes.visite.legendes.<cle>.<n>`.
 */
export interface EtapeSeq {
  d: number;
  l?: string;
  li?: string;
  w?: number;
  p?: string;
  cur?: [number, number];
  clk?: boolean;
}

export const SEQ: ReadonlyArray<ReadonlyArray<EtapeSeq>> = [
  [ { d: 1700, l: 'fr' },
    { d: 1500, p: 'FR' },
    { d: 2800, l: 'en', p: 'FR <em>→ EN</em>' },
    { d: 2300 },
    { d: 1900, l: 'es', p: 'FR <em>→ ES</em>' },
    { d: 2100, l: 'de', p: 'FR <em>→ DE</em>' } ],
  [ { d: 1800, l: 'fr', p: 'FR' },
    { d: 2300 },
    { d: 2600, l: 'en', p: 'FR <em>→ EN</em>' },
    { d: 1900, l: 'es', p: 'FR <em>→ ES</em>' },
    { d: 2100, l: 'de', p: 'FR <em>→ DE</em>' } ],
  [ { d: 1600, l: 'en', li: 'en', p: 'EN', cur: [280, 300] },
    { d: 1900, cur: [497, 62], clk: true },
    { d: 2700, l: 'fr', w: 700, p: 'EN <em>→ FR</em>', cur: [430, 199], clk: true },
    { d: 2000, li: 'fr', cur: [430, 264] },
    { d: 2200 } ],
  [ { d: 2000, l: 'fr' },
    { d: 1600 },
    { d: 3000, l: 'de', w: 500 } ],
  [ { d: 2000, li: 'en', cur: [500, 420] },
    { d: 2000, cur: [400, 120] },
    { d: 2400, li: 'fr', w: 250, cur: [440, 168], clk: true },
    { d: 2800, cur: [372, 262] } ],
];
