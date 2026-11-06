import { afficherErreur, obtenirBandeau, retirerBandeau } from "./contenu/bandeau.ts";
import { ATTR_UI } from "./contenu/commun.ts";
import { demarrerImages, restaurerImages, scannerImages } from "./contenu/images.ts";
import { idPage } from "./lib/page.ts";
import { appliquer, collecter, crochets, estNotreEcriture, restaurerTexte, voisins } from "./contenu/texte.ts";
import { arreterVideos, demarrerVideos } from "./contenu/video.ts";
import { versBackground } from "./pont.ts";
import type { MsgTraduire, ReponseSegments, VersContent } from "./types.ts";

declare global {
  interface Window {
    __precisInjecte?: boolean;
  }
}

const DELAI_REGROUPEMENT_MS = 300;
const TITRE_MAX = 200;

const etat = {
  session: 0,
  langue: "fr",
  texteBloque: false,
  /** Compte inutilisable (crédits, connexion) : ni images ni vidéos ne partent. */
  compteBloque: false,
  enCours: false,
  /** Page traduite (ou en cours) : un second clic ne relance rien. */
  active: false,
  minuteur: 0,
  racines: new Set<Node>(),
  nouveauxElements: false,
};

let observateur: MutationObserver | null = null;
const options: MutationObserverInit = { childList: true, subtree: true, characterData: true };

function surMutations(enregistrements: MutationRecord[]): void {
  for (const e of enregistrements) {
    if (e.type === "characterData") {
      if (!estNotreEcriture(e.target as Text)) etat.racines.add(e.target);
      continue;
    }
    for (const n of e.addedNodes) {
      if (n instanceof Element && n.hasAttribute(ATTR_UI)) continue;
      etat.racines.add(n);
      if (n instanceof Element) etat.nouveauxElements = true;
    }
  }
  if (etat.racines.size > 0 || etat.nouveauxElements) planifier();
}

function planifier(): void {
  if (etat.minuteur) return;
  etat.minuteur = window.setTimeout(() => {
    etat.minuteur = 0;
    void passeTardive();
  }, DELAI_REGROUPEMENT_MS);
}

async function passeTardive(): Promise<void> {
  if (etat.enCours) {
    planifier();
    return;
  }
  const racines = [...etat.racines].filter((n) => n.isConnected);
  const images = etat.nouveauxElements;
  etat.racines.clear();
  etat.nouveauxElements = false;

  etat.enCours = true;
  try {
    if (racines.length > 0) await passeTexte(racines, false);
  } finally {
    etat.enCours = false;
  }
  if (images && !etat.compteBloque) void scannerImages();
}

async function passeTexte(racines: Iterable<Node>, premiere: boolean): Promise<void> {
  if (etat.texteBloque) return;
  const session = etat.session;
  const cibles = collecter(racines);
  if (cibles.length === 0) return;

  const coeurs = [...new Set(cibles.map((c) => c.core))];
  const bandeau = obtenirBandeau();

  // Le titre et, après la première passe, les blocs voisins cadrent la traduction.
  if (premiere) bandeau.progression("Traduction du texte…");
  let rep: ReponseSegments | undefined;
  try {
    rep = await versBackground({
      type: "segments",
      textes: coeurs,
      langue: etat.langue,
      titre: document.title.trim().slice(0, TITRE_MAX),
      contexte: premiere ? [] : voisins(cibles),
      page: idPage(),
    });
  } catch {
    rep = undefined;
  } finally {
    if (premiere && session === etat.session) bandeau.progression(null);
  }
  if (session !== etat.session) return;
  if (!rep?.ok) {
    const code = rep ? rep.erreur : "indisponible";
    if (code === "credits" || code === "deconnecte" || code === "limite") etat.texteBloque = true;
    if (code === "credits" || code === "deconnecte") etat.compteBloque = true;
    afficherErreur(bandeau, code);
    return;
  }

  const traductions = rep.traductions;
  appliquer(cibles, new Map(coeurs.map((c, i) => [c, traductions[i] ?? c])));
  // Écarte les notifications causées par nos propres écritures.
  observateur?.takeRecords();
  if (rep.limite) {
    etat.texteBloque = true;
    afficherErreur(bandeau, "limite");
  }
}

function observer(): void {
  observateur = new MutationObserver(surMutations);
  observateur.observe(document.documentElement, options);
  crochets.surShadow = (racine) => observateur?.observe(racine, options);
}

function arreter(): void {
  etat.session++;
  clearTimeout(etat.minuteur);
  etat.minuteur = 0;
  etat.racines.clear();
  etat.nouveauxElements = false;
  etat.enCours = false;
  etat.texteBloque = false;
  etat.compteBloque = false;
  etat.active = false;
  observateur?.disconnect();
  observateur = null;
  crochets.surShadow = null;
}

function original(): void {
  arreter();
  restaurerTexte();
  restaurerImages();
  arreterVideos();
  retirerBandeau();
}

async function traduire(msg: MsgTraduire): Promise<void> {
  // Même langue, rien de bloqué : on garde le travail fait (et le budget de la page).
  if (etat.active && !etat.texteBloque && msg.langue === etat.langue) {
    if (!etat.enCours && window === window.top) obtenirBandeau().message("Page déjà traduite.");
    return;
  }
  original();
  etat.active = true;
  const session = etat.session;
  etat.langue = msg.langue;

  observer();
  etat.enCours = true;
  try {
    await passeTexte([document], true);
  } finally {
    if (session === etat.session) etat.enCours = false;
  }
  if (session !== etat.session || etat.compteBloque) return;

  demarrerVideos(msg.langue);
  await demarrerImages(msg.langue);
}

if (!window.__precisInjecte) {
  window.__precisInjecte = true;
  chrome.runtime.onMessage.addListener((msg: VersContent) => {
    if (msg.type === "traduire") void traduire(msg);
    else if (msg.type === "original") original();
    return false;
  });
}
