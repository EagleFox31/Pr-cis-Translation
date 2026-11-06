import { API_BASE, SITE, SITE_BIENVENUE } from "./config.ts";
import { decouperEnLots } from "./lib/lots.ts";
import { aEnvoyer, cleImage, empreinteCompte, Memoire } from "./lib/memoire.ts";
import { MagasinIndexedDB } from "./lib/memoire-idb.ts";
import { plusRecente } from "./lib/version.ts";
import type {
  ReponseConnexion,
  ReponseDe,
  ReponseEtat,
  ReponseImage,
  ReponseImageBg,
  ReponseMaj,
  ReponseMemoire,
  ReponseSegments,
  VersBackground,
} from "./types.ts";

type Deconnecte = { erreur: "deconnecte" };

interface ReponseJetons {
  access_token: string;
  refresh_token: string;
  user?: { email?: string };
}

const attente = (ms: number) => new Promise((r) => setTimeout(r, ms));

// --- Jetons : access en session (mémoire du navigateur), refresh en local. Jamais envoyés au content script.

async function enregistrerJetons(acces: string, rafraichissement: string): Promise<void> {
  await chrome.storage.session.set({ access_token: acces });
  await chrome.storage.local.set({ refresh_token: rafraichissement });
}

async function effacerJetons(): Promise<void> {
  await chrome.storage.session.remove("access_token");
  await chrome.storage.local.remove(["refresh_token", "email"]);
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

async function connexion(email: string, motDePasse: string): Promise<ReponseConnexion> {
  try {
    const rep = await fetch(`${API_BASE}/api/auth/login-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password: motDePasse }),
    });
    if (rep.status === 401) return { ok: false, erreur: "identifiants" };
    if (rep.status === 403) return { ok: false, erreur: "non_verifie" };
    if (!rep.ok) return { ok: false, erreur: "indisponible" };
    const jetons = (await rep.json()) as ReponseJetons;
    const adresse = jetons.user?.email ?? email;
    await enregistrerJetons(jetons.access_token, jetons.refresh_token);
    await chrome.storage.local.set({ email: adresse });
    return { ok: true, email: adresse };
  } catch {
    return { ok: false, erreur: "indisponible" };
  }
}

async function deconnexion(): Promise<{ ok: true }> {
  try {
    await appelApi("/api/auth/logout", { method: "POST" });
  } catch {
    // Déconnexion locale quoi qu'il arrive.
  }
  await effacerJetons();
  return { ok: true };
}

async function etat(): Promise<ReponseEtat> {
  const { refresh_token, email } = await chrome.storage.local.get(["refresh_token", "email"]);
  return refresh_token ? { connecte: true, email: email as string | undefined } : { connecte: false };
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

// 413 « page_limit » : la page a épuisé son budget côté serveur ; autre 413 : demande trop grosse.
async function limitePage(rep: Response): Promise<boolean> {
  if (rep.status !== 413) return false;
  try {
    return ((await rep.clone().json()) as { reason?: string }).reason === "page_limit";
  } catch {
    return false;
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
      if (await limitePage(rep)) {
        // Les lots déjà traduits (et payés) s'affichent ; le reste reste en original.
        limite = true;
        break;
      }
      if (rep.status === 413 || rep.status === 429) return { ok: false, erreur: "trop" };
      if (!rep.ok) return { ok: false, erreur: "indisponible" };
      const corps = (await rep.json()) as { traductions: string[] };
      if (corps.traductions.length !== lot.length) return { ok: false, erreur: "indisponible" };
      lot.forEach((texte, i) => connus.set(texte, corps.traductions[i]));
      // Gardé lot par lot : ce lot est payé même si le suivant échoue.
      if (compte) await memoire.garderTextes(compte, langue, lot, corps.traductions);
    }
  } catch {
    return { ok: false, erreur: "indisponible" };
  }
  return { ok: true, traductions: textes.map((t) => connus.get(t) ?? t), limite };
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
    if (connue) return { ok: true, reponse: { ...connue, pages: 0 } };
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
    if (await limitePage(rep)) return { ok: false, erreur: "limite" };
    if (rep.status === 413 || rep.status === 415) return { ok: false, erreur: "refusee" };
    if (!rep.ok) return { ok: false, erreur: "indisponible" };
    const reponse = (await rep.json()) as ReponseImage;
    if (cle && compte) await memoire.garderImage(cle, compte, reponse, JSON.stringify(reponse).length);
    return { ok: true, reponse };
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
    case "connexion":
      return connexion(msg.email, msg.motDePasse);
    case "deconnexion":
      return deconnexion();
    case "etat":
      return etat();
    case "segments":
      return segments(msg.textes, msg.langue, msg.titre, msg.contexte, msg.page);
    case "image":
      return image(msg);
    case "memoire_etat":
      return memoireEtat();
    case "memoire_effacer":
      return memoireEffacer();
    case "maj":
      return verifierMaj();
  }
}

chrome.runtime.onMessage.addListener((msg: VersBackground, _expediteur, repondre) => {
  traiter(msg).then(repondre, () => repondre(undefined));
  return true;
});

// Première installation seulement : page d'accueil du site (épingler, se connecter, essayer).
chrome.runtime.onInstalled.addListener(({ reason }) => {
  if (reason === chrome.runtime.OnInstalledReason.INSTALL) void chrome.tabs.create({ url: SITE_BIENVENUE });
  planifierMaj();
});
chrome.runtime.onStartup.addListener(planifierMaj);
chrome.alarms.onAlarm.addListener(({ name }) => {
  if (name === ALARME_MAJ) void verifierMaj();
});

// Le site demande si l'extension est présente ; le manifest limite déjà l'origine, on la revérifie.
chrome.runtime.onMessageExternal.addListener((msg: unknown, expediteur, repondre) => {
  const type = (msg as { type?: unknown } | null)?.type;
  if (expediteur.origin !== new URL(SITE).origin || type !== "precis-ping") return;
  repondre({ installe: true, version: chrome.runtime.getManifest().version });
});
