import { API_BASE, SITE, SITE_BIENVENUE } from "./config.ts";
import { challengeDe, genererState, genererVerifier, lireRetour, urlAutorisation } from "./connexionSite.ts";
import { decouperEnLots } from "./lib/lots.ts";
import { aEnvoyer, cleImage, empreinteCompte, Memoire } from "./lib/memoire.ts";
import { MagasinIndexedDB } from "./lib/memoire-idb.ts";
import { plusRecente } from "./lib/version.ts";
import { originalOnglet, traduireOnglet } from "./lib/onglet.ts";
import {
  decision,
  ecrireRegle,
  ecrireSuivi,
  LANGUES,
  langueParDefaut,
  lireRegle,
  lireSuivi,
  origineDe,
  resteSuivi,
  type RegleSite,
  type Suivi,
} from "./lib/suivi.ts";
import type {
  MsgAppliquer,
  ReponseDe,
  ReponseEtat,
  ReponseImage,
  ReponseAnalyse,
  ReponseImageBg,
  ReponseMaj,
  ReponseMemoire,
  ReponseSegments,
  VersBackground,
  MsgAccordImages,
  VersContent,
} from "./types.ts";

type Deconnecte = { erreur: "deconnecte" };

interface ReponseJetons {
  access_token: string;
  refresh_token: string;
  user?: { email?: string; plan?: string };
}

const attente = (ms: number) => new Promise((r) => setTimeout(r, ms));

// --- Jetons : access en session (mémoire du navigateur), refresh en local. Jamais envoyés au content script.

async function enregistrerJetons(acces: string, rafraichissement: string): Promise<void> {
  await chrome.storage.session.set({ access_token: acces });
  await chrome.storage.local.set({ refresh_token: rafraichissement });
}

async function effacerJetons(): Promise<void> {
  await chrome.storage.session.remove("access_token");
  await chrome.storage.local.remove(["refresh_token", "email", "plan"]);
}

async function lireAcces(): Promise<string | undefined> {
  const { access_token } = await chrome.storage.session.get("access_token");
  return access_token as string | undefined;
}

let rafraichissement: Promise<boolean> | null = null;

// Faux seulement si le serveur refuse le jeton ; une panne réseau remonte en exception.
async function tenterRafraichissement(): Promise<boolean> {
  const { refresh_token } = await chrome.storage.local.get("refresh_token");
  if (!refresh_token) return false;
  const rep = await fetch(`${API_BASE}/api/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token }),
  });
  if (rep.status === 401 || rep.status === 403) return false;
  if (!rep.ok) throw new Error(`refresh ${rep.status}`);
  const jetons = (await rep.json()) as ReponseJetons;
  await enregistrerJetons(jetons.access_token, jetons.refresh_token);
  return true;
}

function rafraichir(): Promise<boolean> {
  if (!rafraichissement) {
    rafraichissement = tenterRafraichissement().finally(() => {
      rafraichissement = null;
    });
  }
  return rafraichissement;
}

async function appelApi(chemin: string, init: RequestInit = {}): Promise<Response | Deconnecte> {
  const envoyer = async () => {
    const entetes = new Headers(init.headers);
    const jeton = await lireAcces();
    if (jeton) entetes.set("Authorization", `Bearer ${jeton}`);
    return fetch(API_BASE + chemin, { ...init, headers: entetes });
  };

  let rep = await envoyer();
  if (rep.status !== 401) return rep;

  if (!(await rafraichir())) {
    await effacerJetons();
    return { erreur: "deconnecte" };
  }
  rep = await envoyer();
  if (rep.status === 401) {
    await effacerJetons();
    return { erreur: "deconnecte" };
  }
  return rep;
}

async function appelAvecReprises(
  chemin: string,
  init: RequestInit,
  statutsReessayes: number[],
  reprises: number,
  delaiMs: number,
): Promise<Response | Deconnecte> {
  let rep = await appelApi(chemin, init);
  for (let i = 0; i < reprises && rep instanceof Response && statutsReessayes.includes(rep.status); i++) {
    await attente(delaiMs);
    rep = await appelApi(chemin, init);
  }
  return rep;
}

// --- Connexion

// Connexion par le site : un onglet s'ouvre sur la page d'accord, le site renvoie un code
// à usage unique dans le fragment de l'adresse, échangé ici contre les jetons (PKCE).

interface AuthAttente {
  verifier: string;
  state: string;
  tabId: number;
}

const DELAI_FERMETURE_ONGLET_MS = 1500;
// Onglets dont le retour est déjà en cours d'échange : l'onglet signale plusieurs mises à jour pour la même adresse.
const echangesEnCours = new Set<number>();

async function connexionSite(): Promise<{ ok: true }> {
  const verifier = genererVerifier();
  const state = genererState();
  const onglet = await chrome.tabs.create({ url: urlAutorisation(SITE, await challengeDe(verifier), state) });
  if (onglet.id !== undefined) {
    const demande: AuthAttente = { verifier, state, tabId: onglet.id };
    await chrome.storage.session.set({ auth_attente: demande });
  }
  return { ok: true };
}

async function terminerConnexionSite(tabId: number, url: string | undefined): Promise<void> {
  const retour = lireRetour(url, SITE);
  if (!retour || (!retour.code && !retour.erreur) || echangesEnCours.has(tabId)) return;
  // Pris avant tout `await` : deux mises à jour rapprochées du même onglet ne passent pas toutes les deux.
  echangesEnCours.add(tabId);
  try {
    const { auth_attente } = await chrome.storage.session.get("auth_attente");
    const demande = auth_attente as AuthAttente | undefined;
    // Retour étranger (autre onglet, state différent) : ignoré, la demande en cours reste valable.
    if (!demande || demande.tabId !== tabId || retour.state !== demande.state) return;
    // Retour authentique : la demande ne sert qu'une fois.
    await chrome.storage.session.remove("auth_attente");
    if (!retour.code) return; // Refus : l'onglet reste ouvert sur le message du site.
    const rep = await fetch(`${API_BASE}/api/extension/auth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: retour.code, code_verifier: demande.verifier }),
    });
    if (!rep.ok) return;
    const jetons = (await rep.json()) as ReponseJetons;
    await enregistrerJetons(jetons.access_token, jetons.refresh_token);
    await chrome.storage.local.set({ email: jetons.user?.email ?? "", plan: jetons.user?.plan ?? null });
    await attente(DELAI_FERMETURE_ONGLET_MS);
    await chrome.tabs.remove(tabId).catch(() => {}); // Onglet déjà fermé par l'utilisateur.
  } finally {
    echangesEnCours.delete(tabId);
  }
}

chrome.tabs.onUpdated.addListener((tabId, _info, onglet) => {
  void terminerConnexionSite(tabId, onglet.url).catch(() => {}); // Site injoignable : l'utilisateur peut recommencer.
});

async function deconnexion(): Promise<{ ok: true }> {
  try {
    const { refresh_token } = await chrome.storage.local.get("refresh_token");
    if (refresh_token) {
      await fetch(`${API_BASE}/api/extension/auth/deconnexion`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token }),
      });
    }
  } catch {
    // Déconnexion locale quoi qu'il arrive.
  }
  await effacerJetons();
  return { ok: true };
}

async function etat(): Promise<ReponseEtat> {
  const { refresh_token, email, plan } = await chrome.storage.local.get(["refresh_token", "email", "plan"]);
  if (!refresh_token) return { connecte: false };
  return { connecte: true, email: email as string | undefined, plan: (plan as string | null | undefined) ?? undefined };
}

// --- Mémoire : gardée à la déconnexion, séparée par compte.

const memoire = new Memoire(new MagasinIndexedDB());

async function compteActif(): Promise<string | null> {
  const { email } = await chrome.storage.local.get("email");
  return typeof email === "string" && email ? empreinteCompte(email) : null;
}

async function memoireEtat(): Promise<ReponseMemoire> {
  const compte = await compteActif();
  return { traductions: compte ? await memoire.compter(compte) : 0 };
}

async function memoireEffacer(): Promise<ReponseMemoire> {
  const compte = await compteActif();
  if (compte) await memoire.effacer(compte);
  return memoireEtat();
}

// --- Texte

// 413 « page_limit » : limite de la page (ou des pages du jour) atteinte côté serveur ; autre 413 : demande trop grosse.
// Renvoie la limite et l'éventuelle offre Starter/Pro, ou null si ce n'est pas une limite de page.
async function limitePage(rep: Response): Promise<{ limite: string; offre: boolean } | null> {
  if (rep.status !== 413) return null;
  try {
    const corps = (await rep.clone().json()) as { reason?: string; limite?: string; offre?: boolean };
    return corps.reason === "page_limit" ? { limite: corps.limite ?? "", offre: corps.offre === true } : null;
  } catch {
    return null;
  }
}

async function segments(
  textes: string[],
  langue: string,
  titre: string,
  contexte: string[],
  page: string,
): Promise<ReponseSegments> {
  const compte = await compteActif();
  const connus = compte ? await memoire.lireTextes(compte, langue, textes) : new Map<string, string>();
  let limite = false;
  let jour = false;
  let offre = false;
  try {
    for (const lot of decouperEnLots(aEnvoyer(textes, connus))) {
      const rep = await appelAvecReprises(
        "/api/extension/segments",
        {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-Page": page },
          body: JSON.stringify({ textes: lot, langue, titre, contexte }),
        },
        [503],
        2,
        1000,
      );
      if (!(rep instanceof Response)) return { ok: false, erreur: "deconnecte" };
      if (rep.status === 402) return { ok: false, erreur: "credits" };
      const refus = await limitePage(rep);
      if (refus) {
        // Les lots déjà traduits s'affichent ; le reste reste en original.
        limite = true;
        jour = refus.limite === "pages_jour";
        offre = refus.offre;
        break;
      }
      if (rep.status === 413 || rep.status === 429) return { ok: false, erreur: "trop" };
      if (!rep.ok) return { ok: false, erreur: "indisponible" };
      const corps = (await rep.json()) as { traductions: string[]; traduits?: number; limite?: string | null; offre?: boolean };
      if (corps.traductions.length !== lot.length) return { ok: false, erreur: "indisponible" };
      // Lot coupé par la limite : seuls les premiers blocs sont traduits, le reste est resté en original.
      const n = Math.min(corps.traduits ?? lot.length, lot.length);
      lot.slice(0, n).forEach((texte, i) => connus.set(texte, corps.traductions[i]));
      // Gardé lot par lot : ce lot est traduit même si le suivant échoue.
      if (compte) await memoire.garderTextes(compte, langue, lot.slice(0, n), corps.traductions.slice(0, n));
      if (corps.limite) {
        limite = true;
        jour = corps.limite === "pages_jour";
        offre = corps.offre === true;
        break;
      }
    }
  } catch {
    return { ok: false, erreur: "indisponible" };
  }
  return { ok: true, traductions: textes.map((t) => connus.get(t) ?? t), limite, jour, offre };
}

// --- Images

function base64VersOctets(base64: string): Uint8Array<ArrayBuffer> {
  const binaire = atob(base64);
  const octets = new Uint8Array(binaire.length);
  for (let i = 0; i < binaire.length; i++) octets[i] = binaire.charCodeAt(i);
  return octets;
}

function extensionDe(mime: string): string {
  const sous = mime.split("/")[1] ?? "png";
  return sous === "jpeg" ? "jpg" : sous.replace(/[^a-z0-9]/gi, "") || "png";
}

async function lireImage(msg: {
  src?: string;
  donnees?: string;
  mime?: string;
}): Promise<Blob | null> {
  if (msg.src && /^https?:/i.test(msg.src)) {
    try {
      const rep = await fetch(msg.src, { credentials: "include" });
      if (!rep.ok) return null;
      const blob = await rep.blob();
      return blob.type ? blob : new Blob([blob], { type: msg.mime ?? "image/png" });
    } catch {
      return null;
    }
  }
  if (msg.donnees) return new Blob([base64VersOctets(msg.donnees)], { type: msg.mime ?? "image/png" });
  return null;
}

async function image(msg: {
  src?: string;
  donnees?: string;
  mime?: string;
  langue: string;
  page: string;
  sansMemoire?: boolean;
}): Promise<ReponseImageBg> {
  const blob = await lireImage(msg);
  if (!blob) return { ok: false, erreur: "illisible" };

  const compte = msg.sansMemoire ? null : await compteActif();
  const cle = compte ? await cleImage(compte, msg.langue, new Uint8Array(await blob.arrayBuffer())) : null;
  if (cle) {
    const connue = await memoire.lireImage<ReponseImage>(cle);
    if (aDuTexte(connue)) return { ok: true, reponse: { ...connue!, pages: 0 } };
  }

  const formulaire = new FormData();
  formulaire.append("file", blob, `image.${extensionDe(blob.type)}`);
  formulaire.append("langue", msg.langue);
  // Images de vidéo (sans mémoire) : budget à part sur le serveur.
  if (msg.sansMemoire) formulaire.append("video", "true");

  try {
    const rep = await appelAvecReprises(
      "/api/extension/image",
      { method: "POST", body: formulaire, headers: { "X-Page": msg.page } },
      [429, 503],
      3,
      1500,
    );
    if (!(rep instanceof Response)) return { ok: false, erreur: "deconnecte" };
    if (rep.status === 402) return { ok: false, erreur: "credits" };
    const refus = await limitePage(rep);
    if (refus) return { ok: false, erreur: refus.limite === "pages_jour" ? "limite_jour" : "limite", offre: refus.offre };
    if (rep.status === 413 || rep.status === 415) return { ok: false, erreur: "refusee" };
    if (!rep.ok) return { ok: false, erreur: "indisponible" };
    const reponse = (await rep.json()) as ReponseImage;
    // Une image sans texte n'est pas gardée : elle passerait pour traduisible à la prochaine analyse.
    if (cle && compte && aDuTexte(reponse)) await memoire.garderImage(cle, compte, reponse, JSON.stringify(reponse).length);
    return { ok: true, reponse };
  } catch {
    return { ok: false, erreur: "indisponible" };
  }
}

/** Texte lu dans l'image déjà dans la langue cible : même détecteur que pour le texte des pages.
 *  Détection incertaine (texte court) : l'image reste proposée. */
async function dejaEnCible(texte: string | undefined, cible: string): Promise<boolean> {
  if (!texte) return false;
  try {
    const d = await chrome.i18n.detectLanguage(texte);
    return d.isReliable && d.languages[0]?.language.split("-")[0] === cible.split("-")[0];
  } catch {
    return false;
  }
}

function aDuTexte(r: ReponseImage | null): boolean {
  return !!r && r.blocs.length > 0;
}

async function analyseImage(msg: {
  src?: string;
  donnees?: string;
  mime?: string;
  langue: string;
  page: string;
}): Promise<ReponseAnalyse> {
  const blob = await lireImage(msg);
  if (!blob) return { ok: false, erreur: "illisible" };
  // Déjà traduite pour ce compte : traduisible, la traduction sortira de la mémoire.
  const compte = await compteActif();
  const cle = compte ? await cleImage(compte, msg.langue, new Uint8Array(await blob.arrayBuffer())) : null;
  if (cle && aDuTexte(await memoire.lireImage<ReponseImage>(cle))) return { ok: true, traduisible: true };

  const formulaire = new FormData();
  formulaire.append("file", blob, `image.${extensionDe(blob.type)}`);
  formulaire.append("langue", msg.langue);
  try {
    const rep = await appelAvecReprises(
      "/api/extension/image/analyse",
      { method: "POST", body: formulaire, headers: { "X-Page": msg.page } },
      [429, 503],
      3,
      1500,
    );
    if (!(rep instanceof Response)) return { ok: false, erreur: "deconnecte" };
    if (rep.status === 402) return { ok: false, erreur: "credits" };
    const refus = await limitePage(rep);
    if (refus) return { ok: false, erreur: refus.limite === "pages_jour" ? "limite_jour" : "limite", offre: refus.offre };
    if (rep.status === 413 || rep.status === 415) return { ok: false, erreur: "refusee" };
    if (!rep.ok) return { ok: false, erreur: "indisponible" };
    const verdict = (await rep.json()) as { traduisible: boolean; texte?: string };
    if (verdict.traduisible !== true) return { ok: true, traduisible: false };
    return { ok: true, traduisible: !(await dejaEnCible(verdict.texte, msg.langue)) };
  } catch {
    return { ok: false, erreur: "indisponible" };
  }
}

// --- Messages

// --- Mise à jour (installation par dossier : Chrome ne la fait pas seul ; les boutiques, si)

const ALARME_MAJ = "maj";

function planifierMaj(): void {
  void chrome.alarms.create(ALARME_MAJ, { delayInMinutes: 1, periodInMinutes: 360 });
}

async function verifierMaj(): Promise<ReponseMaj> {
  let version: string | null = null;
  try {
    if ((await chrome.management.getSelf()).installType === "development") {
      const rep = await fetch(`${SITE}/extension/version.json`, { cache: "no-store" });
      const distante = rep.ok ? ((await rep.json()) as { version?: unknown }).version : undefined;
      if (typeof distante === "string" && plusRecente(distante, chrome.runtime.getManifest().version)) version = distante;
    }
  } catch {
    // Site injoignable : on retentera à la prochaine vérification.
  }
  await chrome.action.setBadgeText({ text: version ? "1" : "" });
  if (version) await chrome.action.setBadgeBackgroundColor({ color: "#1a4dc7" });
  return { version };
}

function traiter(msg: VersBackground): Promise<ReponseDe<VersBackground>> {
  switch (msg.type) {
    case "connexion-site":
      return connexionSite();
    case "deconnexion":
      return deconnexion();
    case "etat":
      return etat();
    case "segments":
      return segments(msg.textes, msg.langue, msg.titre, msg.contexte, msg.page);
    case "image":
      return image(msg);
    case "analyse_image":
      return analyseImage(msg);
    case "memoire_etat":
      return memoireEtat();
    case "memoire_effacer":
      return memoireEffacer();
    case "maj":
      return verifierMaj();
    case "suivi":
      return Promise.resolve(null);
    case "appliquer":
      return Promise.resolve({ ok: false });
    case "accord_images":
      return Promise.resolve(null);
    default:
      // Message d'une version précédente (script de contenu resté chargé) : ignoré.
      return Promise.resolve(undefined as never);
  }
}

// Onglet traduit ou site « toujours traduire » : un script de contenu enregistré pour son origine
// démarre dans chaque nouveau document (chapitre, cadre, rechargement) et demande la langue au background.
const ID_SUIVI = "precis-suivi";
// Proposition de traduction (option) : cadre principal de toutes les pages web.
const ID_DETECTION = "precis-detection";
let synchro: Promise<void> = Promise.resolve();
function synchroniserScripts(): void {
  synchro = synchro.then(async () => {
    const session = await chrome.storage.session.get(null);
    const local = await chrome.storage.local.get(null);
    const origines = [
      ...new Set([
        ...Object.entries(session)
          .filter(([cle]) => cle.startsWith("suivi:"))
          .map(([, v]) => (v as Suivi).origine),
        ...Object.entries(local)
          .filter(([cle, v]) => cle.startsWith("site:") && (v as RegleSite).mode === "traduire")
          .map(([cle]) => cle.slice("site:".length)),
      ]),
    ];
    // Lève (même de façon synchrone) si rien n'est enregistré : sans effet.
    try {
      await chrome.scripting.unregisterContentScripts({ ids: [ID_SUIVI] });
    } catch {}
    try {
      await chrome.scripting.unregisterContentScripts({ ids: [ID_DETECTION] });
    } catch {}
    if (origines.length > 0) {
      try {
        await chrome.scripting.registerContentScripts([
          {
            id: ID_SUIVI,
            matches: origines.map((o) => o + "/*"),
            allFrames: true,
            runAt: "document_idle",
            js: ["content.js"],
            persistAcrossSessions: true,
          },
        ]);
      } catch {}
    }
    if (local.proposer === true && (await chrome.permissions.contains({ origins: ["<all_urls>"] }))) {
      await chrome.scripting.registerContentScripts([
        {
          id: ID_DETECTION,
          matches: ["http://*/*", "https://*/*"],
          allFrames: false,
          runAt: "document_idle",
          js: ["content.js"],
          persistAcrossSessions: true,
        },
      ]);
    }
  }).catch(() => {}); // Une erreur ne doit pas bloquer les synchronisations suivantes.
}
chrome.storage.onChanged.addListener((changements, zone) => {
  const cles = Object.keys(changements);
  if (zone === "session" && cles.some((c) => c.startsWith("suivi:"))) synchroniserScripts();
  if (zone === "local" && cles.some((c) => c.startsWith("site:") || c === "proposer")) synchroniserScripts();
});
synchroniserScripts();

async function langueChoisie(): Promise<string> {
  const { langue } = await chrome.storage.local.get("langue");
  return typeof langue === "string" && langue ? langue : langueParDefaut(chrome.i18n.getUILanguage(), LANGUES);
}

// Réponse à un nouveau document : langue à appliquer, proposition de traduction, ou rien.
async function reponseSuivi(
  tab: chrome.tabs.Tab,
  cadrePrincipal: boolean,
): Promise<{ langue: string } | { proposer: true; cible: string } | null> {
  const tabId = tab.id;
  if (tabId === undefined) return null;
  let suivi = await lireSuivi(tabId);
  if (suivi && !resteSuivi(suivi, tab.url)) suivi = null;
  const origine = origineDe(tab.url);
  const regle = origine ? await lireRegle(origine) : null;
  const { proposer } = await chrome.storage.local.get("proposer");
  const choix = decision(suivi, regle, proposer === true, cadrePrincipal);
  if (!choix) return null;
  if ("proposer" in choix) return { proposer: true, cible: await langueChoisie() };
  if (!suivi && origine && regle?.mode === "traduire") await ecrireSuivi(tabId, { langue: choix.langue, origine });
  return choix;
}

// Choix du bandeau de proposition : mémorisé pour le site si « toujours », puis appliqué à l'onglet.
async function appliquer(msg: MsgAppliquer, tab: chrome.tabs.Tab | undefined): Promise<boolean> {
  const origine = origineDe(tab?.url);
  if (tab?.id === undefined || !origine) return false;
  if (msg.toujours) {
    await ecrireRegle(origine, msg.mode === "traduire" ? { mode: "traduire", langue: msg.langue } : { mode: "original" });
  }
  if (msg.mode === "traduire") await traduireOnglet(tab.id, msg.langue, origine);
  else await originalOnglet(tab.id, origine);
  return true;
}

// Une seule question par onglet : les cadres qui demandent en même temps partagent la réponse.
const REPONSE_PARTAGEE_MS = 10_000;
const REFUS_PARTAGE_MS = 2_000;
// Les cadres d'une même page finissent leur analyse à quelques instants d'écart : une seule question pour tous.
const REGROUPEMENT_MS = 800;
const accordsEnCours = new Map<number, { images: number; posee: boolean; reponse: Promise<ReponseDe<MsgAccordImages>> }>();

function accordImages(tabId: number, images: number): Promise<ReponseDe<MsgAccordImages>> {
  const enCours = accordsEnCours.get(tabId);
  if (enCours) {
    if (!enCours.posee) enCours.images += images;
    return enCours.reponse;
  }
  const entree = { images, posee: false, reponse: null as unknown as Promise<ReponseDe<MsgAccordImages>> };
  entree.reponse = new Promise<void>((ok) => setTimeout(ok, REGROUPEMENT_MS))
    .then(() => {
      entree.posee = true;
      return chrome.tabs.sendMessage(
        tabId,
        { type: "demander_accord", images: entree.images } satisfies VersContent,
        { frameId: 0 },
      );
    })
    .then((r: ReponseDe<MsgAccordImages> | undefined) => r ?? null, () => null)
    .then((r) => {
      // Les cadres qui finissent leur analyse juste après profitent de la même réponse.
      // Un refus est partagé moins longtemps : la diapositive suivante doit pouvoir reposer la question.
      const duree = !r ? 0 : r.accepte ? REPONSE_PARTAGEE_MS : REFUS_PARTAGE_MS;
      setTimeout(() => accordsEnCours.get(tabId) === entree && accordsEnCours.delete(tabId), duree);
      return r;
    });
  accordsEnCours.set(tabId, entree);
  return entree.reponse;
}

chrome.runtime.onMessage.addListener((msg: VersBackground, expediteur, repondre) => {
  if (msg.type === "accord_images") {
    const id = expediteur.tab?.id;
    if (id === undefined) repondre(null);
    else void accordImages(id, msg.images).then(repondre);
    return true;
  }
  if (msg.type === "suivi") {
    const tab = expediteur.tab;
    if (!tab) repondre(null);
    else void reponseSuivi(tab, expediteur.frameId === 0).then(repondre, () => repondre(null));
    return true;
  }
  if (msg.type === "appliquer") {
    void appliquer(msg, expediteur.tab).then(
      (ok) => repondre({ ok }),
      () => repondre({ ok: false }),
    );
    return true;
  }
  traiter(msg).then(repondre, () => repondre(undefined));
  return true;
});

// Fenêtre ouverte depuis un onglet traduit (window.open) : elle hérite de sa traduction.
chrome.tabs.onCreated.addListener((tab) => {
  if (tab.id === undefined || tab.openerTabId === undefined) return;
  const id = tab.id;
  void lireSuivi(tab.openerTabId).then((suivi) => {
    if (suivi && !suivi.arret) void ecrireSuivi(id, { langue: suivi.langue, origine: suivi.origine });
  });
});

// Onglet parti sur une autre origine : on cesse de le suivre.
chrome.tabs.onUpdated.addListener((tabId, changement, tab) => {
  if (changement.status !== "complete") return;
  void lireSuivi(tabId).then((suivi) => {
    if (suivi && !resteSuivi(suivi, tab.url)) void ecrireSuivi(tabId, null);
  });
});
chrome.tabs.onRemoved.addListener((tabId) => void ecrireSuivi(tabId, null));

// Première installation seulement : page d'accueil du site (épingler, se connecter, essayer).
chrome.runtime.onInstalled.addListener(({ reason }) => {
  if (reason === chrome.runtime.OnInstalledReason.INSTALL) void chrome.tabs.create({ url: SITE_BIENVENUE });
  planifierMaj();
  // La proposition automatique a été retirée : l'ancien réglage ne doit plus rien déclencher.
  void chrome.storage.local.remove("proposer");
  // Forme à rappel : sous Edge, removeAll() ne renvoie pas toujours de promesse.
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({ id: MENU_TRADUIRE, title: "Traduire cette page avec Précis", contexts: ["page"] });
    chrome.contextMenus.create({ id: MENU_ORIGINAL, title: "Afficher l'original (Précis)", contexts: ["page"] });
  });
});
chrome.runtime.onStartup.addListener(planifierMaj);

// Secours quand le bouton de l'extension est inaccessible (fenêtre sans barre) : raccourci et menu contextuel.
const MENU_TRADUIRE = "precis-traduire";
const MENU_ORIGINAL = "precis-original";

async function traduirePage(tab: chrome.tabs.Tab | undefined): Promise<void> {
  const origine = origineDe(tab?.url);
  if (tab?.id === undefined || !origine) return;
  await traduireOnglet(tab.id, await langueChoisie(), origine);
}

async function originalPage(tab: chrome.tabs.Tab | undefined): Promise<void> {
  if (tab?.id !== undefined) await originalOnglet(tab.id, origineDe(tab.url));
}

chrome.commands.onCommand.addListener((commande, tab) => {
  if (commande !== "basculer" || tab?.id === undefined) return;
  void lireSuivi(tab.id)
    .then((suivi) => (suivi && !suivi.arret ? originalPage(tab) : traduirePage(tab)))
    .catch(() => {}); // Page interdite : rien à faire.
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  const action = info.menuItemId === MENU_TRADUIRE ? traduirePage : info.menuItemId === MENU_ORIGINAL ? originalPage : null;
  void action?.(tab).catch(() => {});
});
chrome.alarms.onAlarm.addListener(({ name }) => {
  if (name === ALARME_MAJ) void verifierMaj();
});

// Le site demande si l'extension est présente ; le manifest limite déjà l'origine, on la revérifie.
chrome.runtime.onMessageExternal.addListener((msg: unknown, expediteur, repondre) => {
  const type = (msg as { type?: unknown } | null)?.type;
  if (expediteur.origin !== new URL(SITE).origin || type !== "precis-ping") return;
  repondre({ installe: true, version: chrome.runtime.getManifest().version });
});
