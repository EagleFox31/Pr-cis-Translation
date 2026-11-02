import { libelleMemoire } from "./lib/memoire.ts";
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

function origineDe(url: string | undefined): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    return u.protocol === "http:" || u.protocol === "https:" ? u.origin : null;
  } catch {
    return null;
  }
}

async function afficherVue(): Promise<void> {
  const etat = await versBackground({ type: "etat" });
  vueConnexion.hidden = etat.connecte;
  vueConnecte.hidden = !etat.connecte;
  if (etat.connecte) {
    $("compte").textContent = etat.email ?? "";
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

$("btn-deconnexion").addEventListener("click", async (e) => {
  e.preventDefault();
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
  try {
    await envoyerAuxCadres(tabId, { type: "original" });
    afficher("Page d'origine rétablie.");
  } catch {
    afficher("Rien à rétablir sur cette page.", true);
  }
});

void (async () => {
  [onglet] = await chrome.tabs.query({ active: true, currentWindow: true });
  await afficherVue();
})();
