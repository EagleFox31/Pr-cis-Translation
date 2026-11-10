import { libelleMemoire, libelleTaille } from "./lib/memoire.ts";
import { originalOnglet, traduireOnglet } from "./lib/onglet.ts";
import { cleAccordImages, ecrireRegle, LANGUES, langueParDefaut, lireRegle, origineDe } from "./lib/suivi.ts";
import { SITE } from "./config.ts";
import { versBackground } from "./pont.ts";
import type { ErreurConnexion } from "./types.ts";

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

const vueConnexion = $<HTMLFormElement>("vue-connexion");
const vueConnecte = $<HTMLDivElement>("vue-connecte");
const message = $<HTMLParagraphElement>("message");
const selectLangue = $<HTMLSelectElement>("langue");
const btnTraduire = $<HTMLButtonElement>("btn-traduire");
const caseToujours = $<HTMLInputElement>("toujours");
const caseImages = $<HTMLInputElement>("images-toujours");

const MESSAGES_CONNEXION: Record<ErreurConnexion, string> = {
  identifiants: "Adresse e-mail ou mot de passe incorrect.",
  non_verifie: "Adresse e-mail non vérifiée : confirmez-la depuis le message reçu.",
  indisponible: "Service momentanément indisponible. Réessayez dans un instant.",
};

// Onglet actif lu à l'ouverture : la demande de permission doit partir directement du clic.
let onglet: chrome.tabs.Tab | undefined;

function afficher(texte: string, erreur = false): void {
  message.textContent = texte;
  message.classList.toggle("erreur", erreur);
}

async function afficherVue(): Promise<void> {
  const etat = await versBackground({ type: "etat" });
  vueConnexion.hidden = etat.connecte;
  vueConnecte.hidden = !etat.connecte;
  if (etat.connecte) {
    const email = etat.email ?? "";
    $("compte").textContent = email;
    $("compte").title = email;
    $("initiale").textContent = email.charAt(0);
    const forfait = $("forfait");
    forfait.hidden = !etat.plan;
    forfait.textContent = etat.plan === "free" ? "Forfait gratuit" : `Forfait ${etat.plan ?? ""}`;
    const { langue } = await chrome.storage.local.get("langue");
    selectLangue.value = (langue as string | undefined) ?? langueParDefaut(chrome.i18n.getUILanguage(), LANGUES);
    const origine = origineDe(onglet?.url);
    caseToujours.disabled = !origine;
    caseToujours.checked = origine ? (await lireRegle(origine)) !== null : false;
    caseImages.disabled = !origine;
    caseImages.checked = origine ? Boolean((await chrome.storage.local.get(cleAccordImages(origine)))[cleAccordImages(origine)]) : false;
    afficherMemoire((await versBackground({ type: "memoire_etat" })).traductions);
  }
}

function afficherMemoire(traductions: number): void {
  $("memoire").textContent = libelleMemoire(traductions);
  $("btn-memoire").hidden = traductions === 0;
  // Place occupée par l'extension (mémoire locale surtout) ; vide = 0, même avant que le navigateur ne compacte.
  const taille = $("taille");
  taille.textContent = libelleTaille(0);
  if (traductions > 0) {
    void navigator.storage
      .estimate()
      .then(({ usage }) => (taille.textContent = libelleTaille(usage ?? 0)))
      .catch(() => (taille.textContent = ""));
  }
}

$("btn-memoire").addEventListener("click", async (e) => {
  e.preventDefault();
  try {
    afficherMemoire((await versBackground({ type: "memoire_effacer" })).traductions);
    afficher("");
  } catch {
    afficher("La mémoire n'a pas pu être effacée.", true);
  }
});

vueConnexion.addEventListener("submit", async (e) => {
  e.preventDefault();
  const bouton = $<HTMLButtonElement>("btn-connexion");
  bouton.disabled = true;
  afficher("Connexion…");
  const rep = await versBackground({
    type: "connexion",
    email: $<HTMLInputElement>("email").value.trim(),
    motDePasse: $<HTMLInputElement>("mdp").value,
  });
  bouton.disabled = false;
  if (rep.ok) {
    $<HTMLInputElement>("mdp").value = "";
    afficher("");
    await afficherVue();
  } else {
    afficher(MESSAGES_CONNEXION[rep.erreur], true);
  }
});

$("btn-deconnexion").addEventListener("click", async () => {
  await versBackground({ type: "deconnexion" });
  afficher("");
  await afficherVue();
});

selectLangue.addEventListener("change", async () => {
  void chrome.storage.local.set({ langue: selectLangue.value });
  // Site « toujours traduire » : la règle suit la langue choisie.
  const origine = origineDe(onglet?.url);
  if (!origine || !caseToujours.checked) return;
  if ((await lireRegle(origine))?.mode === "traduire") await ecrireRegle(origine, { mode: "traduire", langue: selectLangue.value });
});

// Cocher enregistre tout de suite « traduire dans la langue choisie » ; Original la change ensuite ; décocher la retire.
caseToujours.addEventListener("change", () => {
  const origine = origineDe(onglet?.url);
  if (!origine) return;
  void ecrireRegle(origine, caseToujours.checked ? { mode: "traduire", langue: selectLangue.value } : null);
});

// Images : cocher accepte d'avance pour le site, décocher fait de nouveau demander.
caseImages.addEventListener("change", () => {
  const origine = origineDe(onglet?.url);
  if (!origine) return;
  const cle = cleAccordImages(origine);
  void (caseImages.checked ? chrome.storage.local.set({ [cle]: true }) : chrome.storage.local.remove(cle));
});


// Bouton « Traduire » en chargement tant qu'un cadre de l'onglet traduit encore :
// un second clic ne peut pas relancer, et l'état se retrouve à la réouverture du popup.
function chargement(actif: boolean): void {
  btnTraduire.disabled = actif;
  btnTraduire.classList.toggle("charge", actif);
  btnTraduire.setAttribute("aria-busy", String(actif));
  btnTraduire.textContent = actif ? "Traduction…" : "Traduire";
}

async function occupe(tabId: number): Promise<boolean> {
  try {
    const res = await chrome.scripting.executeScript({
      target: { tabId, allFrames: true },
      func: () => window.__precisOccupe?.() ?? false,
    });
    return res.some((r) => r.result === true);
  } catch {
    return false;
  }
}

let suivi = 0;
async function suivreTraduction(tabId: number, fin: string): Promise<void> {
  const tour = ++suivi;
  chargement(true);
  // Laisse au contenu le temps de démarrer avant la première lecture.
  await new Promise((r) => setTimeout(r, 400));
  while (tour === suivi && (await occupe(tabId))) {
    await new Promise((r) => setTimeout(r, 700));
  }
  if (tour !== suivi) return;
  chargement(false);
  if (fin) afficher(fin);
}

btnTraduire.addEventListener("click", () => {
  const tabId = onglet?.id;
  const origine = origineDe(onglet?.url);
  if (tabId === undefined || !origine) {
    afficher("Cette page ne peut pas être traduite.", true);
    return;
  }
  const langue = selectLangue.value;
  chargement(true);

  chrome.permissions
    .request({ origins: [origine + "/*"] })
    .then(async (accorde) => {
      if (!accorde) {
        afficher("Accès au site refusé : la page ne peut pas être traduite.", true);
        return;
      }
      await traduireOnglet(tabId, langue, origine);
      if (caseToujours.checked) await ecrireRegle(origine, { mode: "traduire", langue });
      afficher("");
      await suivreTraduction(tabId, "Traduction terminée.");
    })
    .catch(() => afficher("Impossible de traiter cette page.", true))
    .finally(() => chargement(false));
});

$("btn-original").addEventListener("click", async () => {
  const tabId = onglet?.id;
  if (tabId === undefined) return;
  suivi++;
  chargement(false);
  const origine = origineDe(onglet?.url);
  if (origine && caseToujours.checked) await ecrireRegle(origine, { mode: "original" });
  if (await originalOnglet(tabId, origine)) afficher("Page d'origine rétablie.");
  else afficher("Rien à rétablir sur cette page.", true);
});

// Mise à jour : téléchargement direct (le ZIP part en téléchargement, la fenêtre reste ouverte), puis rechargement depuis le dossier.
$("btn-maj-telecharger").addEventListener("click", () => {
  const lien = document.createElement("a");
  lien.href = `${SITE}/extension/precis-extension.zip`;
  lien.download = "precis-extension.zip";
  lien.click();
  afficher("Téléchargement lancé. Décompressez l'archive à la place du dossier actuel, puis cliquez sur « Recharger ».");
});
$("btn-maj-recharger").addEventListener("click", () => chrome.runtime.reload());

async function afficherMaj(): Promise<void> {
  const { version } = await versBackground({ type: "maj" });
  $("maj-version").textContent = version ?? "";
  $("maj").hidden = version === null;
}

void (async () => {
  $("version").textContent = `v${chrome.runtime.getManifest().version}`;
  void afficherMaj();
  [onglet] = await chrome.tabs.query({ active: true, currentWindow: true });
  await afficherVue();
  // Popup rouvert pendant une traduction : le bouton reprend son chargement.
  if (onglet?.id !== undefined && (await occupe(onglet.id))) void suivreTraduction(onglet.id, "Traduction terminée.");
})();
