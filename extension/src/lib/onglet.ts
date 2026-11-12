// Traduire ou rétablir un onglet : partagé par le popup, le raccourci, le menu contextuel et le bandeau.
import { ecrireSuivi, lireRegle } from "./suivi.ts";

export async function traduireOnglet(tabId: number, langue: string, origine: string): Promise<void> {
  await chrome.scripting.executeScript({ target: { tabId, allFrames: true }, files: ["content.js"] });
  await chrome.tabs.sendMessage(tabId, { type: "traduire", langue });
  await ecrireSuivi(tabId, { langue, origine });
}

/** Faux si aucun cadre de l'onglet n'a de contenu à rétablir. */
export async function originalOnglet(tabId: number, origine: string | null): Promise<boolean> {
  // Site « toujours traduire » : l'onglet cesse de traduire, la règle reste.
  const regle = origine ? await lireRegle(origine) : null;
  if (origine && regle?.mode === "traduire") await ecrireSuivi(tabId, { langue: "", origine, arret: true });
  else await ecrireSuivi(tabId, null);
  try {
    await chrome.tabs.sendMessage(tabId, { type: "original" });
    return true;
  } catch {
    return false;
  }
}
