import { libelleMemoire } from "./lib/memoire.ts";
import { ecrireSuivi, origineDe } from "./lib/suivi.ts";
import { SITE } from "./config.ts";
import { versBackground } from "./pont.ts";
import type { ErreurConnexion, VersContent } from "./types.ts";

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

const vueConnexion = $<HTMLFormElement>("vue-connexion");
const vueConnecte = $<HTMLDivElement>("vue-connecte");
const message = $<HTMLParagraphElement>("message");
const selectLangue = $<HTMLSelectElement>("langue");
const btnTraduire = $<HTMLButtonElement>("btn-traduire");

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
    selectLangue.value = (langue as string | undefined) ?? "fr";
    afficherMemoire((await versBackground({ type: "memoire_etat" })).traductions);
  }
}

function afficherMemoire(traductions: number): void {
  $("memoire").textContent = libelleMemoire(traductions);
  $("btn-memoire").hidden = traductions === 0;
}

$("btn-memoire").addEventListener("click", async (e) => {
  e.preventDefault();
  try {
    afficherMemoire((await versBackground({ type: "memoire_effacer" })).traductions);
    afficher("Mémoire effacée : ces pages seront de nouveau comptées.");
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

selectLangue.addEventListener("change", () => {
  void chrome.storage.local.set({ langue: selectLangue.value });
});

async function envoyerAuxCadres(tabId: number, msg: VersContent): Promise<void> {
  await chrome.tabs.sendMessage(tabId, msg);
}

btnTraduire.addEventListener("click", () => {
  const tabId = onglet?.id;
  const origine = origineDe(onglet?.url);
  if (tabId === undefined || !origine) {
    afficher("Cette page ne peut pas être traduite.", true);
    return;
  }
  const langue = selectLangue.value;
  btnTraduire.disabled = true;

  chrome.permissions
    .request({ origins: [origine + "/*"] })
    .then(async (accorde) => {
      if (!accorde) {
        afficher("Accès au site refusé : la page ne peut pas être traduite.", true);
        return;
      }
      await chrome.scripting.executeScript({
        target: { tabId, allFrames: true },
        files: ["content.js"],
      });
      await envoyerAuxCadres(tabId, { type: "traduire", langue });
      await ecrireSuivi(tabId, { langue, origine });
      afficher("Traduction lancée sur la page.");
    })
    .catch(() => afficher("Impossible de traiter cette page.", true))
    .finally(() => {
      btnTraduire.disabled = false;
    });
});

$("btn-original").addEventListener("click", async () => {
  const tabId = onglet?.id;
  if (tabId === undefined) return;
  await ecrireSuivi(tabId, null);
  try {
    await envoyerAuxCadres(tabId, { type: "original" });
    afficher("Page d'origine rétablie.");
  } catch {
    afficher("Rien à rétablir sur cette page.", true);
  }
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
})();
