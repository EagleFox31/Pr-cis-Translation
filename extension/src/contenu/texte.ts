import { aDesBalises, analyser, conforme, sansBalises, type Morceau } from "../lib/balises.ts";
import { aTraduire } from "../lib/filtre.ts";
import { ATTR_UI } from "./commun.ts";

const ATTRIBUTS = ["alt", "title", "placeholder", "aria-label"];
const STRICT = `[translate="no"], .notranslate, [${ATTR_UI}]`;
const IGNORES = `script, style, noscript, code, pre, textarea, input, select, [contenteditable], ${STRICT}`;
// Éléments en ligne : ils restent dans le bloc de leur parent, balisés [[n]]…[[/n]].
const EN_LIGNE = new Set([
  "a", "abbr", "b", "bdi", "bdo", "big", "cite", "data", "del", "dfn", "em", "font", "i", "ins",
  "label", "mark", "nobr", "q", "s", "small", "span", "strong", "sub", "sup", "time", "tt", "u",
  "var", "tspan", "textPath",
]);
// Éléments en ligne opaques : gardés tels quels, balise vide [[n]][[/n]].
const ATOMES = new Set([
  "br", "wbr", "img", "picture", "svg", "math", "canvas", "video", "audio", "iframe", "object",
  "embed", "input", "select", "textarea", "code", "kbd", "samp",
]);

// Un parent du bloc (le conteneur ou un élément en ligne) et ses enfants d'origine.
interface Niveau {
  parent: Node;
  noeuds: ChildNode[];
  ancre: ChildNode | null; // nœud qui suit le bloc ; null : jusqu'à la fin du parent
  donnees: Map<Text, string>;
  crees: Text[];
}

// Suite d'enfants en ligne d'un conteneur (p, li, td, div à texte direct…),
// envoyée en un seul texte balisé.
export interface Bloc {
  genre: "bloc";
  parent: Node;
  core: string;
  debut: string;
  fin: string;
  table: Element[]; // n → table[n - 1]
  parents: Map<number, number>;
  vides: Set<number>;
  niveaux: Map<Node, Niveau>;
}

export type Cible = Bloc | { genre: "attr"; el: Element; attr: string; avant: string; core: string };

interface Trace {
  original: string;
  traduit: string;
}

// Les nœuds texte d'origine sont réutilisés (jamais retirés) : les scripts de
// page qui les tiennent (React…) restent cohérents.
const ecrits = new WeakMap<Text, string>();
let blocs: Bloc[] = [];
const attributs = new Map<Element, Map<string, Trace>>();

// Appelé pour chaque shadow root ouvert rencontré (pour y brancher l'observateur).
export const crochets: { surShadow: ((racine: ShadowRoot) => void) | null } = { surShadow: null };

const ESPACES = /[ \t\n\r\f]+/g;

class Collecte {
  readonly cibles: Cible[] = [];
  private readonly vus = new Set<Node>();
  private readonly attrsVus = new Map<Element, Set<string>>();
  private readonly enLigneCache = new Map<Element, boolean>();

  attributs(el: Element): void {
    for (const attr of ATTRIBUTS) {
      const avant = el.getAttribute(attr);
      if (avant === null || (attr === "title" && el.hasAttribute("data-precis-titre"))) continue;
      const vus = this.attrsVus.get(el) ?? new Set<string>();
      this.attrsVus.set(el, vus);
      if (vus.has(attr)) continue;
      vus.add(attr);
      const core = avant.trim();
      if (!aTraduire(core) || attributs.get(el)?.get(attr)?.traduit === avant) continue;
      this.cibles.push({ genre: "attr", el, attr, avant, core });
    }
  }

  // Renvoie vrai si l'on doit descendre dans l'élément.
  entrer(el: Element): boolean {
    if (el.matches(STRICT)) return false;
    if (el.matches(IGNORES)) {
      if (el.matches("input, textarea")) this.attributs(el);
      return false;
    }
    this.attributs(el);
    if (el.shadowRoot) {
      crochets.surShadow?.(el.shadowRoot);
      this.conteneur(el.shadowRoot);
    }
    return true;
  }

  private atome(el: Element): boolean {
    return ATOMES.has(el.localName) || !!el.shadowRoot || el.matches(IGNORES);
  }

  // En ligne : élément de texte sans descendant de type bloc.
  private enLigne(el: Element): boolean {
    let r = this.enLigneCache.get(el);
    if (r === undefined) {
      r = ATOMES.has(el.localName) ||
        (EN_LIGNE.has(el.localName) && (el.matches(IGNORES) || [...el.children].every((e) => this.enLigne(e))));
      this.enLigneCache.set(el, r);
    }
    return r;
  }

  // Attributs et contenus propres (svg, shadow root) d'un élément pris dans un bloc.
  private prendreEnLigne(el: Element): void {
    if (this.atome(el)) {
      if (this.entrer(el)) this.conteneur(el);
      return;
    }
    this.attributs(el);
    for (const enfant of el.children) this.prendreEnLigne(enfant);
  }

  conteneur(racine: Node): void {
    if (this.vus.has(racine)) return;
    this.vus.add(racine);
    let suite: ChildNode[] = [];
    const fermer = () => {
      if (suite.length > 0) this.bloc(racine, suite);
      suite = [];
    };
    for (const n of [...racine.childNodes]) {
      if (n instanceof Element) {
        if (this.enLigne(n)) {
          suite.push(n);
          this.prendreEnLigne(n);
        } else {
          fermer();
          if (this.entrer(n)) this.conteneur(n);
        }
      } else if (n instanceof CharacterData) {
        suite.push(n);
      }
    }
    fermer();
  }

  private bloc(parent: Node, noeuds: ChildNode[]): void {
    const b: Bloc = {
      genre: "bloc", parent, core: "", debut: "", fin: "",
      table: [], parents: new Map(), vides: new Set(), niveaux: new Map(),
    };
    const etat = { etranger: false, piege: false };
    const brut = this.serialiser(b, parent, noeuds, noeuds[noeuds.length - 1].nextSibling, 0, etat)
      .replace(/ {2,}/g, " ");
    // Rien de neuf (tout vient de nous) ou texte qui contient déjà des balises.
    if (!etat.etranger || etat.piege || !aTraduire(sansBalises(brut).trim())) return;
    b.core = brut.trim();
    b.debut = /^\s*/.exec(brut)?.[0] ?? "";
    b.fin = /\s*$/.exec(brut)?.[0] ?? "";
    this.cibles.push(b);
  }

  private serialiser(
    b: Bloc,
    parent: Node,
    noeuds: ChildNode[],
    ancre: ChildNode | null,
    nParent: number,
    etat: { etranger: boolean; piege: boolean },
  ): string {
    const niveau: Niveau = { parent, noeuds, ancre, donnees: new Map(), crees: [] };
    b.niveaux.set(parent, niveau);
    let s = "";
    for (const n of noeuds) {
      if (n instanceof Text) {
        niveau.donnees.set(n, n.data);
        if (aDesBalises(n.data)) etat.piege = true;
        if (/\p{L}/u.test(n.data) && !estNotreEcriture(n)) etat.etranger = true;
        s += n.data.replace(ESPACES, " ");
      } else if (n instanceof Element) {
        const num = b.table.push(n);
        b.parents.set(num, nParent);
        if (this.atome(n)) {
          b.vides.add(num);
          s += `[[${num}]][[/${num}]]`;
        } else {
          s += `[[${num}]]${this.serialiser(b, n, [...n.childNodes], null, num, etat)}[[/${num}]]`;
        }
      }
    }
    return s;
  }

  visiter(racine: Node): void {
    if (racine.parentElement?.closest(IGNORES)) return;
    // Un texte ou un élément en ligne se traduit avec tout son bloc.
    let n = racine;
    while (n.parentNode && (n instanceof CharacterData || (n instanceof Element && this.enLigne(n)))) {
      n = n.parentNode;
    }
    if (n instanceof Element) {
      if (this.entrer(n)) this.conteneur(n);
    } else {
      this.conteneur(n);
    }
  }
}

function nettoyer(): void {
  blocs = blocs.filter((b) => b.parent.isConnected);
  for (const el of attributs.keys()) if (!el.isConnected) attributs.delete(el);
}

export function collecter(racines: Iterable<Node>): Cible[] {
  nettoyer();
  const collecte = new Collecte();
  for (const racine of racines) collecte.visiter(racine);
  return collecte.cibles;
}

// Blocs voisins (texte nu, déjà traduit ou non) : contexte des passes tardives.
export function voisins(cibles: Cible[], max = 4000): string[] {
  const vus = new Set<string>();
  let total = 0;
  for (const c of cibles) {
    const el = c.genre === "bloc" ? c.parent : c.el;
    if (!(el instanceof Element)) continue;
    for (const v of [el.previousElementSibling, el.nextElementSibling]) {
      if (!v || v.hasAttribute(ATTR_UI)) continue;
      const texte = (v.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 300);
      if (!aTraduire(texte) || vus.has(texte)) continue;
      if (total + texte.length > max) return [...vus];
      vus.add(texte);
      total += texte.length;
    }
  }
  return [...vus];
}

function intact(b: Bloc): boolean {
  for (const [parent, niveau] of b.niveaux) {
    if (!niveau.noeuds.every((n) => n.parentNode === parent)) return false;
    if (niveau.ancre && niveau.ancre.parentNode !== parent) return false;
    // Rien d'inséré entre le premier nœud du bloc et son ancre.
    let compte = 0;
    for (let n: ChildNode | null = niveau.noeuds[0]; n && n !== niveau.ancre; n = n.nextSibling) compte++;
    if (compte !== niveau.noeuds.length) return false;
    for (const [t, data] of niveau.donnees) if (t.data !== data) return false;
  }
  return true;
}

function ecrire(t: Text, valeur: string): void {
  t.data = valeur;
  ecrits.set(t, valeur);
}

function enOrdre(parent: Node, ordre: ChildNode[], ancre: ChildNode | null): boolean {
  let n = ordre[0];
  if (!n || n.parentNode !== parent) return false;
  for (const suivant of ordre.slice(1)) {
    if (n.nextSibling !== suivant) return false;
    n = suivant;
  }
  return n.nextSibling === ancre;
}

// Place la traduction d'un niveau : textes d'origine réutilisés dans l'ordre,
// éléments d'origine (attributs, écouteurs gardés), surplus vidés en fin de parent.
function poser(b: Bloc, parent: Node, morceaux: Morceau[]): void {
  const niveau = b.niveaux.get(parent)!;
  const libres = niveau.noeuds.filter((n): n is Text => n instanceof Text);
  const places: ChildNode[] = [];
  for (const m of morceaux) {
    if (typeof m === "string") {
      let t = libres.shift();
      if (!t) {
        t = document.createTextNode("");
        niveau.crees.push(t);
      }
      ecrire(t, m);
      places.push(t);
    } else {
      const el = b.table[m.n - 1];
      if (!b.vides.has(m.n)) poser(b, el, m.enfants);
      places.push(el);
    }
  }
  for (const t of libres) ecrire(t, "");
  const ordre = [...places, ...niveau.noeuds.filter((n) => !places.includes(n))];
  if (!enOrdre(parent, ordre, niveau.ancre)) for (const n of ordre) parent.insertBefore(n, niveau.ancre);
}

export function appliquer(cibles: Cible[], traductions: Map<string, string>): void {
  for (const c of cibles) {
    const traduction = traductions.get(c.core)?.trim();
    if (!traduction || traduction === c.core) continue;

    if (c.genre === "bloc") {
      // Balises perdues ou déplacées : le bloc reste en original.
      const arbre = analyser(c.debut + traduction + c.fin);
      if (!arbre || !conforme(arbre, c.parents, c.vides) || !intact(c)) continue;
      poser(c, c.parent, arbre);
      blocs.push(c);
    } else {
      if (c.el.getAttribute(c.attr) !== c.avant) continue;
      const debut = /^\s*/.exec(c.avant)?.[0] ?? "";
      const fin = /\s*$/.exec(c.avant)?.[0] ?? "";
      const valeur = debut + traduction + fin;
      c.el.setAttribute(c.attr, valeur);
      const traces = attributs.get(c.el) ?? new Map<string, Trace>();
      traces.set(c.attr, { original: c.avant, traduit: valeur });
      attributs.set(c.el, traces);
    }
  }
}

// Vrai si le nœud contient encore exactement ce que nous y avons écrit.
export function estNotreEcriture(noeud: Text): boolean {
  const ecrit = ecrits.get(noeud);
  return ecrit !== undefined && ecrit === noeud.data;
}

export function restaurerTexte(): void {
  for (const b of blocs.reverse()) {
    for (const [parent, niveau] of b.niveaux) {
      for (const t of niveau.crees) if (estNotreEcriture(t)) t.remove();
      for (const [t, data] of niveau.donnees) if (estNotreEcriture(t)) t.data = data;
      const enPlace = niveau.noeuds.every((n) => n.parentNode === parent) &&
        (niveau.ancre === null || niveau.ancre.parentNode === parent);
      if (enPlace && !enOrdre(parent, niveau.noeuds, niveau.ancre)) {
        for (const n of niveau.noeuds) parent.insertBefore(n, niveau.ancre);
      }
    }
  }
  for (const [el, traces] of attributs) {
    for (const [attr, trace] of traces) {
      if (el.getAttribute(attr) === trace.traduit) el.setAttribute(attr, trace.original);
    }
  }
  blocs = [];
  attributs.clear();
}
