import { ATTR_UI } from "./commun.ts";

// Éléments posés au-dessus d'une cible (image traduite, bouton vidéo), repositionnés au défilement.
const actifs = new Map<HTMLElement, Element>();
let planifie = false;

function placer(el: HTMLElement, cible: Element): void {
  const r = cible.getBoundingClientRect();
  Object.assign(el.style, {
    left: `${r.left + window.scrollX}px`,
    top: `${r.top + window.scrollY}px`,
    width: `${r.width}px`,
    height: `${r.height}px`,
  });
}

function replacer(): void {
  planifie = false;
  for (const [el, cible] of actifs) {
    if (!cible.isConnected) {
      el.remove();
      actifs.delete(el);
    } else {
      placer(el, cible);
    }
  }
  if (actifs.size === 0) ecouter(false);
}

function demander(): void {
  if (planifie) return;
  planifie = true;
  requestAnimationFrame(replacer);
}

function ecouter(actif: boolean): void {
  const methode = actif ? "addEventListener" : "removeEventListener";
  window[methode]("scroll", demander, { capture: true, passive: true });
  window[methode]("resize", demander, { passive: true });
}

export function poserCalque(cible: Element, el: HTMLElement): () => void {
  el.setAttribute(ATTR_UI, "");
  Object.assign(el.style, { position: "absolute", margin: "0", zIndex: "2147483646", boxSizing: "border-box" });
  placer(el, cible);
  document.documentElement.appendChild(el);
  if (actifs.size === 0) ecouter(true);
  actifs.set(el, cible);
  return () => {
    el.remove();
    actifs.delete(el);
    if (actifs.size === 0) ecouter(false);
  };
}

export function retirerCalques(): void {
  for (const el of actifs.keys()) el.remove();
  actifs.clear();
  ecouter(false);
}
