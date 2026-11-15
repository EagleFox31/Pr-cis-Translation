// Mémoire locale des traductions déjà payées (le serveur garde aussi 30 jours les images traduites).
// La logique reste ici, sans navigateur ; l'accès à IndexedDB est dans memoire-idb.ts.

// À incrémenter quand le moteur change assez pour rendre les anciennes traductions caduques.
const VERSION = "v1";
const JOUR_MS = 24 * 60 * 60 * 1000;
const INTERVALLE_PURGE_MS = 60 * 1000;

export type Genre = "textes" | "images";

export interface Borne {
  ageMaxMs: number;
  entreesMax?: number;
  octetsMax?: number;
}

export const BORNES: Record<Genre, Borne> = {
  textes: { ageMaxMs: 30 * JOUR_MS, entreesMax: 50_000 },
  images: { ageMaxMs: 30 * JOUR_MS, octetsMax: 200 * 1024 * 1024 },
};

export interface Meta {
  cle: string;
  utilise: number;
  taille: number;
}

export interface EntreeMemoire {
  cle: string;
  compte: string;
  valeur: unknown;
  taille: number;
}

export interface Magasin {
  /** Lit les entrées connues et note leur dernier usage. */
  lire(genre: Genre, cles: string[], maintenant: number): Promise<Map<string, unknown>>;
  ecrire(genre: Genre, entrees: EntreeMemoire[], maintenant: number): Promise<void>;
  metas(genre: Genre): Promise<Meta[]>;
  supprimer(genre: Genre, cles: string[]): Promise<void>;
  compter(compte: string): Promise<number>;
  effacer(compte: string): Promise<void>;
}

const encodeur = new TextEncoder();

/** SHA-256 en hexadécimal. Chaque partie est préfixée de sa longueur : ("ab","c") ≠ ("a","bc"). */
export async function empreinte(...parties: (string | Uint8Array)[]): Promise<string> {
  const morceaux = parties.flatMap((p) => {
    const octets = typeof p === "string" ? encodeur.encode(p) : p;
    return [encodeur.encode(`${octets.length}:`), octets];
  });
  const tout = new Uint8Array(morceaux.reduce((n, m) => n + m.length, 0));
  let position = 0;
  for (const m of morceaux) {
    tout.set(m, position);
    position += m.length;
  }
  const hache = new Uint8Array(await crypto.subtle.digest("SHA-256", tout));
  return Array.from(hache, (o) => o.toString(16).padStart(2, "0")).join("");
}

/** L'adresse n'est jamais écrite en clair dans la base : seule son empreinte y figure. */
export const empreinteCompte = (email: string): Promise<string> =>
  empreinte(VERSION, "compte", email.trim().toLowerCase());

export const cleTexte = (compte: string, langue: string, texte: string): Promise<string> =>
  empreinte(VERSION, "texte", compte, langue, texte);

export const cleImage = (compte: string, langue: string, octets: Uint8Array): Promise<string> =>
  empreinte(VERSION, "image", compte, langue, octets);

/** Textes à demander au serveur : inconnus, et une seule fois chacun. */
export function aEnvoyer(textes: string[], connus: Map<string, string>): string[] {
  return [...new Set(textes)].filter((t) => !connus.has(t));
}

/** Clés à retirer : trop anciennes, puis les moins récemment utilisées tant qu'une borne est dépassée. */
export function aEvincer(metas: Meta[], borne: Borne, maintenant: number): string[] {
  const parUsage = [...metas].sort((a, b) => a.utilise - b.utilise);
  let entrees = parUsage.length;
  let octets = parUsage.reduce((n, m) => n + m.taille, 0);
  const retirees: string[] = [];
  for (const m of parUsage) {
    const tropVieille = maintenant - m.utilise > borne.ageMaxMs;
    const tropDEntrees = borne.entreesMax !== undefined && entrees > borne.entreesMax;
    const tropDOctets = borne.octetsMax !== undefined && octets > borne.octetsMax;
    if (!tropVieille && !tropDEntrees && !tropDOctets) break;
    retirees.push(m.cle);
    entrees -= 1;
    octets -= m.taille;
  }
  return retirees;
}

export function libelleMemoire(n: number): string {
  if (n === 0) return "Mémoire : vide";
  return `Mémoire : ${n.toLocaleString("fr-FR")} traduction${n > 1 ? "s" : ""}`;
}

/** Taille lisible : « 0 o », « 840 Ko », « 2,4 Mo ». */
export function libelleTaille(octets: number): string {
  const unites = ["o", "Ko", "Mo", "Go"];
  let v = octets;
  let i = 0;
  while (v >= 1024 && i < unites.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toLocaleString("fr-FR", { maximumFractionDigits: v < 10 && i > 0 ? 1 : 0 })} ${unites[i]}`;
}

/** Une panne de la mémoire ne doit jamais empêcher une traduction : tout échec vaut « rien de connu ». */
export class Memoire {
  private magasin: Magasin;
  private horloge: () => number;
  private dernierePurge = 0;

  constructor(magasin: Magasin, horloge: () => number = Date.now) {
    this.magasin = magasin;
    this.horloge = horloge;
  }

  async lireTextes(compte: string, langue: string, textes: string[]): Promise<Map<string, string>> {
    const connus = new Map<string, string>();
    try {
      const uniques = [...new Set(textes)];
      const cles = await Promise.all(uniques.map((t) => cleTexte(compte, langue, t)));
      const trouves = await this.magasin.lire("textes", cles, this.horloge());
      uniques.forEach((t, i) => {
        const valeur = trouves.get(cles[i]);
        if (typeof valeur === "string") connus.set(t, valeur);
      });
    } catch {
      connus.clear();
    }
    return connus;
  }

  /** Une réponse égale à l'original n'est pas gardée : c'est aussi la réponse d'un échec de balises. */
  async garderTextes(compte: string, langue: string, envoyes: string[], recus: string[]): Promise<void> {
    try {
      const paires = envoyes.map((t, i) => [t, recus[i]] as const).filter(([t, r]) => r !== t);
      const entrees = await Promise.all(
        paires.map(async ([t, r]) => ({
          cle: await cleTexte(compte, langue, t),
          compte,
          valeur: r,
          taille: r.length,
        })),
      );
      if (entrees.length) await this.magasin.ecrire("textes", entrees, this.horloge());
      await this.purgerSiBesoin();
    } catch {
      // Déjà payé mais non gardé : la traduction est tout de même affichée.
    }
  }

  async lireImage<T>(cle: string): Promise<T | null> {
    try {
      const trouves = await this.magasin.lire("images", [cle], this.horloge());
      return (trouves.get(cle) as T | undefined) ?? null;
    } catch {
      return null;
    }
  }

  async garderImage(cle: string, compte: string, valeur: unknown, taille: number): Promise<void> {
    try {
      await this.magasin.ecrire("images", [{ cle, compte, valeur, taille }], this.horloge());
      await this.purgerSiBesoin();
    } catch {
      // Voir garderTextes.
    }
  }

  async compter(compte: string): Promise<number> {
    try {
      return await this.magasin.compter(compte);
    } catch {
      return 0;
    }
  }

  effacer(compte: string): Promise<void> {
    return this.magasin.effacer(compte);
  }

  private async purgerSiBesoin(): Promise<void> {
    const maintenant = this.horloge();
    if (maintenant - this.dernierePurge < INTERVALLE_PURGE_MS) return;
    this.dernierePurge = maintenant;
    for (const genre of ["textes", "images"] as const) {
      const cles = aEvincer(await this.magasin.metas(genre), BORNES[genre], maintenant);
      if (cles.length) await this.magasin.supprimer(genre, cles);
    }
  }
}
