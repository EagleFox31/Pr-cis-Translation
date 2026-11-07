import { DetecteurAnimation } from "../lib/animation.ts";
import { messageAccord, messageLimiteImages } from "../lib/cout.ts";
import { enParallele } from "../lib/parallele.ts";
import { afficherErreur, obtenirBandeau } from "./bandeau.ts";
import { poserCalque, retirerCalques } from "./calques.ts";
import {
  analyserImage,
  ATTR_UI,
  blobVersCharge,
  canvasVersCharge,
  elementsProfonds,
  envoyerImage,
  estHttp,
  type Charge,
} from "./commun.ts";
import type { ErreurImage, ReponseAnalyse, ReponseImage } from "../types.ts";

const TAILLE_MIN = 64;
/** Images traitées à la fois : le serveur en accepte autant par utilisateur. */
const PARALLELE = 2;

type Genre = "img" | "fond" | "canvas";

interface Candidat {
  el: Element;
  genre: Genre;
  cle: string;
  src?: string;
}

type Accord = "inconnu" | "attente" | "oui" | "non";

const etat = {
  accord: "inconnu" as Accord, enCours: false, analyse: false, aRefaire: false,
  /** Crédits, session ou service : plus d'envoi jusqu'à la prochaine traduction. */
  bloque: false,
  session: 0, langue: "fr", total: 0, fait: 0,
};
/** Bilan de la page : images traduisibles vues, images remplacées, budget du serveur épuisé. */
const bilan = { vues: 0, traduites: 0, limite: false };

let traites = new WeakMap<Element, Set<string>>();
let file = new Map<Element, Candidat>();
let restaurations: (() => void)[] = [];
const resultats = new Map<string, ReponseImage>();
/** Envois en cours par adresse : une même image affichée deux fois ne part qu'une fois. */
const enVol = new Map<string, ReturnType<typeof envoyerImage>>();
/** Analyses par langue et adresse : une même image n'est analysée qu'une fois. */
const analyses = new Map<string, Promise<ReponseAnalyse>>();
/** Images visibles en cours d'analyse : pas encore dans la file. */
const enAnalyse = new Set<Element>();

const detecteur = new DetecteurAnimation();
const identifiants = new WeakMap<Element, number>();
let prochainId = 0;
let observateurSrc: MutationObserver | null = null;
let minuteurChargement = 0;

const identifiant = (el: Element): number => {
  let id = identifiants.get(el);
  if (id === undefined) {
    id = ++prochainId;
    identifiants.set(el, id);
  }
  return id;
};

function marquer(el: Element, ...cles: (string | null)[]): void {
  const connues = traites.get(el) ?? new Set<string>();
  for (const cle of cles) if (cle) connues.add(cle);
  traites.set(el, connues);
}

function urlFond(el: Element): string | null {
  const valeur = getComputedStyle(el).backgroundImage;
  const m = /url\((['"]?)(.*?)\1\)/.exec(valeur);
  if (!m?.[2]) return null;
  try {
    return new URL(m[2], document.baseURI).href;
  } catch {
    return null;
  }
}

function cleDe(el: Element, genre: Genre): string | null {
  if (genre === "img") return (el as HTMLImageElement).currentSrc || (el as HTMLImageElement).src || null;
  if (genre === "fond") return urlFond(el);
  return "canvas";
}

function trouverCandidats(): Candidat[] {
  const trouves: Candidat[] = [];
  const ajouter = (el: Element, genre: Genre, src?: string) => {
    const cle = cleDe(el, genre);
    if (!cle || traites.get(el)?.has(cle) || file.has(el) || enAnalyse.has(el)) return;
    trouves.push({ el, genre, cle, src });
  };

  for (const el of elementsProfonds(document)) {
    if (el.hasAttribute(ATTR_UI)) continue;
    if (el instanceof HTMLImageElement) {
      // Taille du fichier et taille affichée : une icône de 50 px n'a pas de texte lisible.
      // Seules les images à l'écran : chaque traduction coûte un crédit.
      const r = el.getBoundingClientRect();
      const ok = el.complete && el.naturalWidth >= TAILLE_MIN && el.naturalHeight >= TAILLE_MIN
        && r.width >= TAILLE_MIN && r.height >= TAILLE_MIN && aireVisible(el) > 0;
      if (ok && !detecteur.estAnime(identifiant(el))) {
        ajouter(el, "img", el.currentSrc || el.src);
      }
    } else if (el instanceof HTMLCanvasElement) {
      if (el.width >= TAILLE_MIN && el.height >= TAILLE_MIN && aireVisible(el) > 0) ajouter(el, "canvas");
    } else if (el instanceof HTMLElement) {
      const r = el.getBoundingClientRect();
      if (r.width < TAILLE_MIN || r.height < TAILLE_MIN || aireVisible(el) === 0) continue;
      const url = urlFond(el);
      if (url) ajouter(el, "fond", url);
    }
  }
  return trouves;
}

function aireVisible(el: Element): number {
  const r = el.getBoundingClientRect();
  const l = Math.min(r.right, window.innerWidth) - Math.max(r.left, 0);
  const h = Math.min(r.bottom, window.innerHeight) - Math.max(r.top, 0);
  return l > 0 && h > 0 ? l * h : 0;
}

function plusVisible(): Candidat {
  let meilleur: Candidat | undefined;
  let aire = -1;
  for (const c of file.values()) {
    const a = aireVisible(c.el);
    if (a > aire) {
      meilleur = c;
      aire = a;
    }
  }
  return meilleur!;
}

// --- Application du résultat

function appliquer(c: Candidat, rep: ReponseImage): void {
  if (rep.remplacee && rep.image) {
    bilan.traduites++;
    const uri = `data:${rep.mime};base64,${rep.image}`;
    if (c.genre === "img") remplacerImg(c.el as HTMLImageElement, uri);
    else if (c.genre === "fond") remplacerFond(c.el as HTMLElement, uri);
    else superposer(c.el, uri);
    observateurSrc?.takeRecords();
    return;
  }
  const titre = rep.blocs.map((b) => b.traduction).filter(Boolean).join(" · ");
  if (!titre) return;
  const precedent = c.el.getAttribute("title");
  c.el.setAttribute("title", titre);
  c.el.setAttribute("data-precis-titre", "");
  restaurations.push(() => {
    if (precedent === null) c.el.removeAttribute("title");
    else c.el.setAttribute("title", precedent);
    c.el.removeAttribute("data-precis-titre");
  });
}

function remplacerImg(img: HTMLImageElement, uri: string): void {
  const src = img.getAttribute("src");
  const srcset = img.getAttribute("srcset");
  const sources = [...(img.parentElement?.tagName === "PICTURE" ? img.parentElement.querySelectorAll("source") : [])]
    .map((s) => ({ s, srcset: s.getAttribute("srcset") }));
  img.removeAttribute("srcset");
  for (const { s } of sources) s.removeAttribute("srcset");
  img.src = uri;
  restaurations.push(() => {
    if (src === null) img.removeAttribute("src");
    else img.setAttribute("src", src);
    if (srcset !== null) img.setAttribute("srcset", srcset);
    for (const { s, srcset: valeur } of sources) if (valeur !== null) s.setAttribute("srcset", valeur);
  });
}

function remplacerFond(el: HTMLElement, uri: string): void {
  const valeur = el.style.getPropertyValue("background-image");
  const priorite = el.style.getPropertyPriority("background-image");
  el.style.setProperty("background-image", `url("${uri}")`);
  restaurations.push(() => {
    if (valeur) el.style.setProperty("background-image", valeur, priorite);
    else el.style.removeProperty("background-image");
  });
}

function superposer(canvas: Element, uri: string): void {
  const calque = document.createElement("img");
  calque.src = uri;
  Object.assign(calque.style, { pointerEvents: "none", objectFit: "fill" });
  restaurations.push(poserCalque(canvas, calque));
}

// --- Traitement

async function lireLocalement(src: string): Promise<Charge | null> {
  try {
    const rep = await fetch(src);
    return rep.ok ? await blobVersCharge(await rep.blob()) : null;
  } catch {
    return null;
  }
}

async function preparer(c: Candidat): Promise<Charge | null> {
  if (c.genre === "canvas") return canvasVersCharge(c.el as HTMLCanvasElement);
  const src = c.src ?? "";
  if (estHttp(src)) return { src };
  if (/^(data|blob):/i.test(src)) return lireLocalement(src);
  return null;
}

type Envoi = { ok: true } | { ok: false; erreur: ErreurImage };

/** Le background n'a pas toujours accès à l'hôte de l'image : seconde chance depuis la page. */
async function avecSecondeChance<R extends Envoi>(charge: Charge, envoyer: (ch: Charge) => Promise<R>): Promise<R> {
  const rep = await envoyer(charge);
  if (rep.ok || (rep as Envoi & { ok: false }).erreur !== "illisible" || !charge.src) return rep;
  const locale = await lireLocalement(charge.src);
  return locale ? envoyer(locale) : rep;
}

/** Erreur du serveur : vrai s'il faut tout arrêter (crédits, session, panne, budget de page). */
function echec(c: Candidat, erreur: ErreurImage): boolean {
  if (erreur === "refusee" || erreur === "illisible") {
    marquer(c.el, c.cle);
    return false;
  }
  if (erreur === "limite") {
    // Seules les images à texte remplacées ont usé le budget : on le dit en chiffres.
    bilan.limite = true;
    obtenirBandeau().message(messageLimiteImages(bilan.traduites, bilan.vues));
  } else {
    afficherErreur(obtenirBandeau(), erreur);
  }
  etat.bloque = true;
  return true;
}

type Verdict = "traduisible" | "sans texte" | "arret";

/** Analyse serveur (sans débit) : seules les images traduisibles entrent dans la file. */
async function analyser(c: Candidat, session: number): Promise<Verdict> {
  if (c.genre === "img" && detecteur.estAnime(identifiant(c.el))) return "sans texte";
  if (c.src && resultats.has(c.src)) return "traduisible";
  const vol = c.src ? `${etat.langue} ${c.src}` : null;
  let promesse = vol ? analyses.get(vol) : undefined;
  if (!promesse) {
    const charge = await preparer(c);
    if (!charge) return "sans texte";
    promesse = avecSecondeChance(charge, (ch) => analyserImage(etat.langue, ch));
    if (vol) {
      analyses.set(vol, promesse);
      // Une erreur passagère ne reste pas en mémoire.
      void promesse.then((r) => !r.ok && analyses.delete(vol));
    }
  }
  const rep = await promesse;
  if (session !== etat.session) return "arret";
  if (!rep.ok) return echec(c, rep.erreur) ? "arret" : "sans texte";
  return rep.traduisible ? "traduisible" : "sans texte";
}

// Renvoie vrai s'il faut arrêter la file (crédits épuisés, session expirée, service en panne).
async function traiter(c: Candidat, session: number): Promise<boolean> {
  if (c.genre === "img" && detecteur.estAnime(identifiant(c.el))) return false;

  const mise = c.src ? resultats.get(c.src) : undefined;
  let reponse = mise ?? null;

  let charge: Awaited<ReturnType<typeof preparer>> = null;
  if (!reponse) {
    charge = await preparer(c);
    // L'autre travailleur a pu traduire la même image pendant la préparation.
    reponse = (c.src && resultats.get(c.src)) || null;
  }

  if (!reponse) {
    if (!charge) {
      marquer(c.el, c.cle);
      return false;
    }
    const envoi = () => avecSecondeChance(charge!, (ch) => envoyerImage(etat.langue, ch));
    const vol = c.src ? `${etat.langue} ${c.src}` : null;
    let promesse = vol ? enVol.get(vol) : undefined;
    if (!promesse) {
      promesse = envoi();
      if (vol) {
        enVol.set(vol, promesse);
        void promesse.finally(() => enVol.delete(vol));
      }
    }
    const rep = await promesse;
    if (session !== etat.session) return true;
    if (!rep.ok) return echec(c, rep.erreur);
    reponse = rep.reponse;
    if (c.src) resultats.set(c.src, reponse);
  }

  appliquer(c, reponse);
  marquer(c.el, c.cle, cleDe(c.el, c.genre), reponse.image ? `data:${reponse.mime};base64,${reponse.image}` : null);
  return false;
}

async function boucle(): Promise<void> {
  if (etat.enCours) return;
  etat.enCours = true;
  const session = etat.session;
  try {
    // Le plus visible d'abord, repris à chaque place libérée (l'utilisateur a pu défiler).
    const prendre = (): Candidat | undefined => {
      while (file.size > 0 && session === etat.session) {
        const c = plusVisible();
        file.delete(c.el);
        // Sortie de l'écran entre-temps : abandonnée, reprise au prochain défilement.
        if (!c.el.isConnected || aireVisible(c.el) === 0) {
          etat.total--;
          bilan.vues--;
          continue;
        }
        etat.fait++;
        return c;
      }
      return undefined;
    };
    await enParallele(PARALLELE, prendre, async (c) => {
      obtenirBandeau().progression(`Traduction… ${etat.fait}/${etat.total}`);
      if (await traiter(c, session)) {
        // Une session plus récente a sa propre file : on ne la vide pas.
        if (session === etat.session) file.clear();
        return true;
      }
      return false;
    });
  } finally {
    if (session === etat.session) {
      etat.enCours = false;
      etat.fait = 0;
      etat.total = 0;
      obtenirBandeau().progression(null);
    }
  }
}

/** Analyse les images visibles, deux à la fois ; vrai s'il faut tout arrêter. */
async function analyserVisibles(session: number): Promise<boolean> {
  const candidats = trouverCandidats();
  if (candidats.length === 0) return false;
  for (const c of candidats) enAnalyse.add(c.el);
  if (!etat.enCours) obtenirBandeau().progression("Analyse des images…");
  let arret = false;
  let i = 0;
  try {
    await enParallele(PARALLELE, () => candidats[i++], async (c) => {
      const verdict = await analyser(c, session);
      if (verdict === "arret") return (arret = true);
      if (verdict === "sans texte") marquer(c.el, c.cle);
      else {
        file.set(c.el, c);
        etat.total++;
        bilan.vues++;
        // Accord déjà donné : traduite sans attendre la fin de l'analyse.
        if (etat.accord === "oui") void boucle();
      }
      return false;
    });
  } finally {
    // Une session plus récente a vidé puis rempli son propre ensemble.
    if (session === etat.session) {
      for (const c of candidats) enAnalyse.delete(c.el);
      if (!etat.enCours) obtenirBandeau().progression(null);
    }
  }
  return arret;
}

export async function scannerImages(): Promise<void> {
  if (etat.accord === "non" || bilan.limite || etat.bloque) return;
  // Une analyse à la fois : un défilement pendant l'analyse la relance à la fin.
  if (etat.analyse) {
    etat.aRefaire = true;
    return;
  }
  const session = etat.session;
  etat.analyse = true;
  let arret: boolean;
  try {
    arret = await analyserVisibles(session);
  } finally {
    if (session === etat.session) etat.analyse = false;
  }
  if (session !== etat.session) return;
  if (arret) {
    file.clear();
    return;
  }
  if (etat.aRefaire) {
    etat.aRefaire = false;
    relancer();
  }
  // Aucune image traduisible : rien à proposer.
  if (file.size === 0) return;

  if (etat.accord === "inconnu") {
    etat.accord = "attente";
    const cle = `accord:${location.origin}`;
    const stock = await chrome.storage.local.get(cle);
    if (session !== etat.session) return;
    if (stock[cle]) {
      etat.accord = "oui";
    } else {
      const reponse = await obtenirBandeau().demanderAccord(messageAccord(file.size));
      if (session !== etat.session) return;
      if (!reponse.accepte) {
        etat.accord = "non";
        file.clear();
        return;
      }
      if (reponse.toujours) await chrome.storage.local.set({ [cle]: true });
      etat.accord = "oui";
    }
  }
  if (etat.accord === "oui") void boucle();
}

function relancer(): void {
  clearTimeout(minuteurChargement);
  minuteurChargement = window.setTimeout(() => void scannerImages(), 300);
}

function surChargement(e: Event): void {
  if (e.target instanceof HTMLImageElement) relancer();
}

// Défilement (page ou bloc interne), fenêtre redimensionnée, clic (diapo suivante, onglet) :
// de nouvelles images peuvent arriver à l'écran.
const EVENEMENTS_VUE = ["scroll", "resize", "click"] as const;

/** Vrai tant que la file d'images de ce cadre se traite (bouton du popup en chargement). */
export function imagesEnCours(): boolean {
  return etat.enCours || etat.analyse;
}

export function demarrerImages(langue: string): Promise<void> {
  arreterImages();
  etat.langue = langue;
  observateurSrc = new MutationObserver((enregistrements) => {
    for (const e of enregistrements) {
      if (e.target instanceof HTMLImageElement && !e.target.hasAttribute(ATTR_UI)) {
        detecteur.changement(identifiant(e.target), Date.now());
      }
    }
  });
  observateurSrc.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["src"],
    subtree: true,
  });
  document.addEventListener("load", surChargement, true);
  for (const nom of EVENEMENTS_VUE) window.addEventListener(nom, relancer, { capture: true, passive: true });
  return scannerImages();
}

function arreterImages(): void {
  etat.session++;
  etat.accord = "inconnu";
  etat.enCours = false;
  etat.analyse = false;
  etat.aRefaire = false;
  etat.bloque = false;
  etat.total = 0;
  etat.fait = 0;
  Object.assign(bilan, { vues: 0, traduites: 0, limite: false });
  file = new Map();
  enAnalyse.clear();
  clearTimeout(minuteurChargement);
  observateurSrc?.disconnect();
  observateurSrc = null;
  document.removeEventListener("load", surChargement, true);
  for (const nom of EVENEMENTS_VUE) window.removeEventListener(nom, relancer, { capture: true });
}

export function restaurerImages(): void {
  arreterImages();
  for (const restaurer of restaurations.reverse()) restaurer();
  restaurations = [];
  retirerCalques();
  traites = new WeakMap();
  resultats.clear();
  analyses.clear();
}
