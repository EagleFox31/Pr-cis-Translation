import { SITE_TARIFS } from "../config.ts";
import { ATTR_UI } from "./commun.ts";
import { THEME } from "./theme.ts";

export interface Accord {
  accepte: boolean;
  toujours: boolean;
}

export interface Bandeau {
  progression(texte: string | null): void;
  message(texte: string, lien?: { libelle: string; href: string }): void;
  demanderAccord(texte: string): Promise<Accord>;
}

const STYLE = `${THEME}
  [hidden] { display: none !important; }
  .barre { pointer-events: auto; display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px;
    box-sizing: border-box; max-width: 680px; margin: 0 auto 12px; padding: 12px 16px;
    background: var(--navy); color: var(--white); font: 13px/1.45 var(--police);
    border-radius: 12px; box-shadow: 0 10px 40px rgba(13,27,62,.35); }
  .barre span.texte { flex: 1 1 260px; }
  .barre a { color: var(--gold-light); font-weight: 600; }
  .barre a:focus-visible { outline: 2px solid var(--gold-light); outline-offset: 2px; }
  .barre label { display: flex; align-items: center; gap: 6px; }
  .barre input[type="checkbox"] { margin: 0; accent-color: var(--blue-bright); }
  button { font-size: 13px; font-weight: 600; line-height: 1; padding: 8px 14px; border-radius: 9px;
    cursor: pointer; border: 1px solid transparent; background: var(--blue); color: var(--white);
    transition: background .15s ease, border-color .15s ease; }
  button:hover { background: var(--blue-bright); }
  button.secondaire { background: transparent; color: rgba(255,255,255,.85); border-color: rgba(255,255,255,.35); }
  button.secondaire:hover { color: var(--white); border-color: var(--white); }
  .pastille { position: fixed; top: 12px; right: 12px; pointer-events: none; padding: 6px 12px;
    background: rgba(13,27,62,.92); color: var(--white); border-radius: 999px;
    box-shadow: 0 4px 16px rgba(13,27,62,.25); font: 500 12px/1.3 var(--police); }
`;

let courant: { hote: HTMLElement; api: Bandeau } | null = null;

function bouton(libelle: string, secondaire: boolean, action: () => void): HTMLButtonElement {
  const b = document.createElement("button");
  b.type = "button";
  b.textContent = libelle;
  if (secondaire) b.className = "secondaire";
  b.addEventListener("click", action);
  return b;
}

function creer(): { hote: HTMLElement; api: Bandeau } {
  const hote = document.createElement("div");
  hote.setAttribute(ATTR_UI, "");
  hote.style.cssText =
    "all:initial;position:fixed;left:0;right:0;bottom:0;z-index:2147483647;pointer-events:none;";
  const racine = hote.attachShadow({ mode: "closed" });
  racine.innerHTML = `<style>${STYLE}</style><div class="barre" hidden></div><div class="pastille" hidden></div>`;
  const barre = racine.querySelector<HTMLDivElement>(".barre")!;
  const pastille = racine.querySelector<HTMLDivElement>(".pastille")!;
  let accordEnCours = false;

  const texte = (contenu: string) => {
    const s = document.createElement("span");
    s.className = "texte";
    s.textContent = contenu;
    return s;
  };

  const api: Bandeau = {
    progression(t) {
      pastille.hidden = t === null;
      if (t !== null) pastille.textContent = t;
    },

    message(t, lien) {
      if (accordEnCours) return;
      const elements: Node[] = [texte(t)];
      if (lien) {
        const a = document.createElement("a");
        a.href = lien.href;
        a.target = "_blank";
        a.rel = "noopener";
        a.textContent = lien.libelle;
        elements.push(a);
      }
      elements.push(bouton("Fermer", true, () => (barre.hidden = true)));
      barre.replaceChildren(...elements);
      barre.hidden = false;
    },

    demanderAccord(t) {
      accordEnCours = true;
      return new Promise<Accord>((resolve) => {
        const caseToujours = document.createElement("input");
        caseToujours.type = "checkbox";
        const etiquette = document.createElement("label");
        etiquette.append(caseToujours, "Toujours pour ce site");
        const repondre = (accepte: boolean) => {
          accordEnCours = false;
          barre.hidden = true;
          resolve({ accepte, toujours: accepte && caseToujours.checked });
        };
        barre.replaceChildren(
          texte(t),
          etiquette,
          bouton("Traduire les images", false, () => repondre(true)),
          bouton("Pas maintenant", true, () => repondre(false)),
        );
        barre.hidden = false;
      });
    },
  };

  document.documentElement.appendChild(hote);
  return { hote, api };
}

export function obtenirBandeau(): Bandeau {
  courant ??= creer();
  return courant.api;
}

export function retirerBandeau(): void {
  courant?.hote.remove();
  courant = null;
}

export function afficherErreur(bandeau: Bandeau, erreur: string): void {
  switch (erreur) {
    case "credits":
      bandeau.message("Crédits épuisés.", { libelle: "Voir les offres", href: SITE_TARIFS });
      break;
    case "deconnecte":
      bandeau.message("Reconnectez-vous dans l'extension.");
      break;
    case "trop":
      bandeau.message("Trop de demandes : réessayez dans un instant.");
      break;
    default:
      bandeau.message("Service momentanément indisponible. Réessayez plus tard.");
  }
}
