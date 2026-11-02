import { afficherErreur, obtenirBandeau } from "./bandeau.ts";
import { poserCalque } from "./calques.ts";
import { canvasVersCharge, envoyerImage } from "./commun.ts";

const TAILLE_MIN = 64;

const STYLE = `
  button { position: absolute; top: 8px; left: 8px; pointer-events: auto; padding: 5px 10px;
    font: 12px/1.3 system-ui, -apple-system, "Segoe UI", sans-serif; color: #fff; background: rgba(31,41,55,.92);
    border: 1px solid rgba(255,255,255,.6); border-radius: 6px; cursor: pointer; }
  button:disabled { cursor: default; opacity: .85; }
`;

let langue = "fr";
const actifs = new Map<HTMLVideoElement, () => void>();

function nettoyer(video: HTMLVideoElement): void {
  actifs.get(video)?.();
  actifs.delete(video);
}

function image(video: HTMLVideoElement): Promise<{ donnees?: string; mime?: string } | null> {
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  try {
    canvas.getContext("2d")?.drawImage(video, 0, 0);
  } catch {
    return Promise.resolve(null);
  }
  return canvasVersCharge(canvas);
}

function afficherBouton(video: HTMLVideoElement): void {
  const hote = document.createElement("div");
  hote.style.pointerEvents = "none";
  const racine = hote.attachShadow({ mode: "closed" });
  racine.innerHTML = `<style>${STYLE}</style><button type="button">Traduire cette image</button>`;
  const bouton = racine.querySelector("button")!;

  const retraits: (() => void)[] = [poserCalque(video, hote)];
  actifs.set(video, () => retraits.forEach((r) => r()));

  bouton.addEventListener("click", async () => {
    bouton.disabled = true;
    bouton.textContent = "Traduction…";
    const charge = await image(video);
    if (!charge) {
      bouton.textContent = "Image non traduisible";
      return;
    }
    const rep = await envoyerImage(langue, charge, true);
    if (!actifs.has(video)) return;

    if (!rep.ok) {
      if (rep.erreur === "refusee") {
        bouton.textContent = "Image refusée";
        return;
      }
      afficherErreur(obtenirBandeau(), rep.erreur);
      bouton.textContent = "Traduire cette image";
      bouton.disabled = false;
      return;
    }
    if (!rep.reponse.remplacee || !rep.reponse.image) {
      bouton.textContent = "Aucun texte à traduire";
      return;
    }
    const calque = document.createElement("img");
    calque.src = `data:${rep.reponse.mime};base64,${rep.reponse.image}`;
    const style = getComputedStyle(video);
    Object.assign(calque.style, {
      pointerEvents: "none",
      objectFit: style.objectFit,
      objectPosition: style.objectPosition,
    });
    retraits.push(poserCalque(video, calque));
    // Le bouton reste au-dessus du calque.
    retraits.push(poserCalque(video, hote));
    bouton.textContent = "Image traduite";
  });
}

function surPause(e: Event): void {
  const video = e.target;
  if (!(video instanceof HTMLVideoElement) || actifs.has(video)) return;
  if (video.clientWidth < TAILLE_MIN || video.clientHeight < TAILLE_MIN || video.videoWidth === 0) return;
  afficherBouton(video);
}

function surLecture(e: Event): void {
  if (e.target instanceof HTMLVideoElement) nettoyer(e.target);
}

export function demarrerVideos(langueCible: string): void {
  arreterVideos();
  langue = langueCible;
  document.addEventListener("pause", surPause, true);
  document.addEventListener("play", surLecture, true);
}

export function arreterVideos(): void {
  document.removeEventListener("pause", surPause, true);
  document.removeEventListener("play", surLecture, true);
  for (const video of [...actifs.keys()]) nettoyer(video);
}
