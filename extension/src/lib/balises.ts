// Blocs balisés (étude extension §4) : chaque élément en ligne d'un bloc y est
// un numéro `[[n]]…[[/n]]`, que le moteur garde en traduisant.

export type Morceau = string | { n: number; enfants: Morceau[] };

const BALISE = /\[\[(\/?)(\d+)\]\]/g;

export const aDesBalises = (texte: string): boolean => /\[\[\/?\d+\]\]/.test(texte);

export const sansBalises = (texte: string): string => texte.replace(/\[\[\/?\d+\]\]/g, "");

// Arbre du texte, ou null si une balise est orpheline, mal imbriquée ou répétée.
export function analyser(texte: string): Morceau[] | null {
  const racine: Morceau[] = [];
  const pile: { n: number; enfants: Morceau[] }[] = [];
  const vus = new Set<number>();
  const courant = () => (pile.length > 0 ? pile[pile.length - 1].enfants : racine);
  let dernier = 0;

  for (const m of texte.matchAll(BALISE)) {
    const debut = m.index ?? 0;
    if (debut > dernier) courant().push(texte.slice(dernier, debut));
    dernier = debut + m[0].length;
    const n = Number(m[2]);
    if (m[1]) {
      if (pile.pop()?.n !== n) return null;
    } else {
      if (vus.has(n)) return null;
      vus.add(n);
      const el = { n, enfants: [] };
      courant().push(el);
      pile.push(el);
    }
  }
  if (pile.length > 0) return null;
  if (dernier < texte.length) courant().push(texte.slice(dernier));
  return racine;
}

// Vrai si l'arbre garde exactement les éléments attendus, chacun sous son
// parent d'origine (0 = le bloc), et les `vides` (image, saut de ligne…) sans texte.
export function conforme(arbre: Morceau[], parents: Map<number, number>, vides: Set<number>): boolean {
  let vus = 0;
  const verifier = (morceaux: Morceau[], parent: number): boolean =>
    morceaux.every((m) => {
      if (typeof m === "string") return true;
      if (parents.get(m.n) !== parent) return false;
      vus++;
      if (vides.has(m.n)) return m.enfants.every((e) => typeof e === "string" && e.trim() === "");
      return verifier(m.enfants, m.n);
    });
  return verifier(arbre, 0) && vus === parents.size;
}
