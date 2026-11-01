import { aTraduire } from "../lib/filtre.ts";
import { ATTR_UI } from "./commun.ts";

const ATTRIBUTS = ["alt", "title", "placeholder", "aria-label"];
const STRICT = `[translate="no"], .notranslate, [${ATTR_UI}]`;
const IGNORES = `script, style, noscript, code, pre, textarea, input, select, [contenteditable], ${STRICT}`;

export type Cible =
  | { genre: "texte"; noeud: Text; avant: string; core: string }
  | { genre: "attr"; el: Element; attr: string; avant: string; core: string };

interface Trace {
  original: string;
  traduit: string;
}

const textes = new Map<Text, Trace>();
const attributs = new Map<Element, Map<string, Trace>>();

// Appelé pour chaque shadow root ouvert rencontré (pour y brancher l'observateur).
export const crochets: { surShadow: ((racine: ShadowRoot) => void) | null } = { surShadow: null };

class Collecte {
  readonly cibles: Cible[] = [];
  private readonly textesVus = new Set<Text>();
  private readonly attrsVus = new Map<Element, Set<string>>();

  texte(noeud: Text): void {
    if (this.textesVus.has(noeud)) return;
    this.textesVus.add(noeud);
    const avant = noeud.data;
    const core = avant.trim();
    if (!aTraduire(core) || textes.get(noeud)?.traduit === avant) return;
    this.cibles.push({ genre: "texte", noeud, avant, core });
  }

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
      this.marcher(el.shadowRoot);
    }
    return true;
  }

  marcher(racine: Node): void {
    const marcheur = document.createTreeWalker(racine, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
      acceptNode: (n) =>
        n.nodeType === Node.TEXT_NODE
          ? NodeFilter.FILTER_ACCEPT
          : this.entrer(n as Element)
            ? NodeFilter.FILTER_SKIP
            : NodeFilter.FILTER_REJECT,
    });
    while (marcheur.nextNode()) this.texte(marcheur.currentNode as Text);
  }

  visiter(racine: Node): void {
    if (racine.parentElement?.closest(IGNORES)) return;
    if (racine instanceof Text) {
      this.texte(racine);
    } else if (racine instanceof Element) {
      if (this.entrer(racine)) this.marcher(racine);
    } else {
      this.marcher(racine);
    }
  }
}

function nettoyer(): void {
  for (const noeud of textes.keys()) if (!noeud.isConnected) textes.delete(noeud);
  for (const el of attributs.keys()) if (!el.isConnected) attributs.delete(el);
}

export function collecter(racines: Iterable<Node>): Cible[] {
  nettoyer();
  const collecte = new Collecte();
  for (const racine of racines) collecte.visiter(racine);
  return collecte.cibles;
}

export function appliquer(cibles: Cible[], traductions: Map<string, string>): void {
  for (const c of cibles) {
    const traduction = traductions.get(c.core)?.trim();
    if (!traduction || traduction === c.core) continue;
    const debut = /^\s*/.exec(c.avant)?.[0] ?? "";
    const fin = /\s*$/.exec(c.avant)?.[0] ?? "";
    const valeur = debut + traduction + fin;

    if (c.genre === "texte") {
      if (!c.noeud.isConnected || c.noeud.data !== c.avant) continue;
      c.noeud.data = valeur;
      textes.set(c.noeud, { original: c.avant, traduit: valeur });
    } else {
      if (c.el.getAttribute(c.attr) !== c.avant) continue;
      c.el.setAttribute(c.attr, valeur);
      const traces = attributs.get(c.el) ?? new Map<string, Trace>();
      traces.set(c.attr, { original: c.avant, traduit: valeur });
      attributs.set(c.el, traces);
    }
  }
}

// Vrai si le nœud contient encore exactement ce que nous y avons écrit.
export function estNotreEcriture(noeud: Text): boolean {
  return textes.get(noeud)?.traduit === noeud.data;
}

export function restaurerTexte(): void {
  for (const [noeud, trace] of textes) {
    if (noeud.data === trace.traduit) noeud.data = trace.original;
  }
  for (const [el, traces] of attributs) {
    for (const [attr, trace] of traces) {
      if (el.getAttribute(attr) === trace.traduit) el.setAttribute(attr, trace.original);
    }
  }
  textes.clear();
  attributs.clear();
}
