import { versBackground } from "../pont.ts";
import type { ReponseImageBg } from "../types.ts";

// Marque les éléments injectés par l'extension : jamais traduits ni analysés.
export const ATTR_UI = "data-precis-ui";

export interface Charge {
  src?: string;
  donnees?: string;
  mime?: string;
}

export const estHttp = (url: string): boolean => /^https?:/i.test(url);

export async function envoyerImage(langue: string, charge: Charge, sansMemoire = false): Promise<ReponseImageBg> {
  try {
    const rep = await versBackground({ type: "image", langue, sansMemoire, ...charge });
    return rep ?? { ok: false, erreur: "indisponible" };
  } catch {
    return { ok: false, erreur: "indisponible" };
  }
}

export function blobVersCharge(blob: Blob): Promise<Charge | null> {
  return new Promise((resolve) => {
    const lecteur = new FileReader();
    lecteur.onload = () => {
      const donnees = String(lecteur.result).split(",")[1];
      resolve(donnees ? { donnees, mime: blob.type || "image/png" } : null);
    };
    lecteur.onerror = () => resolve(null);
    lecteur.readAsDataURL(blob);
  });
}

// Null si le canvas est contaminé (image d'une autre origine sans autorisation).
export function canvasVersCharge(canvas: HTMLCanvasElement): Promise<Charge | null> {
  return new Promise((resolve) => {
    try {
      canvas.toBlob((blob) => resolve(blob ? blobVersCharge(blob) : null), "image/png");
    } catch {
      resolve(null);
    }
  });
}

// Parcourt le document et les shadow roots ouverts.
export function elementsProfonds(racine: ParentNode, sortie: Element[] = []): Element[] {
  for (const el of racine.querySelectorAll("*")) {
    sortie.push(el);
    if (el.shadowRoot) elementsProfonds(el.shadowRoot, sortie);
  }
  return sortie;
}
