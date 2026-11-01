import { afficherErreur, obtenirBandeau, retirerBandeau } from "./contenu/bandeau.ts";
import { ATTR_UI } from "./contenu/commun.ts";
import { demarrerImages, restaurerImages, scannerImages } from "./contenu/images.ts";
import { creerMoteur, ErreurPrecis, type Moteur } from "./contenu/moteur.ts";
import { appliquer, collecter, crochets, estNotreEcriture, restaurerTexte } from "./contenu/texte.ts";
import { arreterVideos, demarrerVideos } from "./contenu/video.ts";
import type { MsgTraduire, VersContent } from "./types.ts";

declare global {
  interface Window {
    __precisInjecte?: boolean;
  }
}

const DELAI_REGROUPEMENT_MS = 300;
const TAILLE_ECHANTILLON = 2000;
const MESSAGE_NAVIGATEUR =
  "Traduction du navigateur indisponible ici — cochez Qualité Précis (crédits)";

const etat = {
  session: 0,
  langue: "fr",
  qualitePrecis: false,
  moteur: null as Moteur | null,
  texteBloque: false,
  enCours: false,
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
  if (images) void scannerImages();
}

async function passeTexte(racines: Iterable<Node>, premiere: boolean): Promise<void> {
  if (etat.texteBloque) return;
  const session = etat.session;
  const cibles = collecter(racines);
  if (cibles.length === 0) return;

  const coeurs = [...new Set(cibles.map((c) => c.core))];
  const bandeau = obtenirBandeau();

  if (!etat.moteur) {
    const echantillon = coeurs.join(" ").slice(0, TAILLE_ECHANTILLON);
    const resultat = await creerMoteur(etat.langue, etat.qualitePrecis, echantillon);
    if (session !== etat.session) return;
    if (!resultat.ok) {
      etat.texteBloque = true;
      bandeau.message(
        resultat.raison === "meme_langue"
          ? "La page est déjà dans la langue choisie : texte non traduit."
          : MESSAGE_NAVIGATEUR,
      );
      return;
    }
    etat.moteur = resultat.moteur;
  }

  if (premiere) bandeau.progression("Traduction du texte…");
  let traductions: string[];
  try {
    traductions = await etat.moteur.traduire(coeurs, (n, total) => {
      if (premiere) bandeau.progression(`Traduction du texte… ${n}/${total}`);
    });
  } catch (e) {
    if (session !== etat.session) return;
    const code = e instanceof ErreurPrecis ? e.code : "indisponible";
    if (code === "credits" || code === "deconnecte") etat.texteBloque = true;
    afficherErreur(bandeau, code);
    return;
  } finally {
    if (premiere && session === etat.session) bandeau.progression(null);
  }
  if (session !== etat.session) return;

  appliquer(cibles, new Map(coeurs.map((c, i) => [c, traductions[i] ?? c])));
  // Écarte les notifications causées par nos propres écritures.
  observateur?.takeRecords();
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
  etat.moteur = null;
  etat.texteBloque = false;
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
  original();
  const session = etat.session;
  etat.langue = msg.langue;
  etat.qualitePrecis = msg.qualitePrecis;

  observer();
  etat.enCours = true;
  try {
    await passeTexte([document], true);
  } finally {
    if (session === etat.session) etat.enCours = false;
  }
  if (session !== etat.session) return;

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
