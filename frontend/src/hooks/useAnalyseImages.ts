import { useEffect, useState } from 'react';

import { authHeader, refreshAccessToken } from '../services/api';
import { postAvecFichier } from '../services/depot';

const API_KEY = import.meta.env.VITE_API_KEY || '';
const API_BASE = import.meta.env.VITE_API_BASE || '';

/** Formats dont le serveur sait lire et remplacer les images. */
const FORMATS_AVEC_IMAGES = ['pdf', 'docx', 'pptx', 'xlsx'];

export interface AnalyseImages {
  /** Pages comptées pour le texte. Peut valoir 0 : document fait d'images. */
  pages: number;
  /** Images où du texte a été détecté. */
  images: number;
  analysees: number;
  total: number;
  /** Toutes les images n'ont pas pu être lues : seules les autres sont proposées. */
  incomplet: boolean;
  /** Lecture des images impossible pour le moment. */
  indisponible: boolean;
  /** Langue probable du document ('en', 'fr'…), absente si incertaine. */
  langue?: string | null;
}

export const formatAvecImages = (ext: string) => FORMATS_AVEC_IMAGES.includes(ext);

/**
 * Cherche le texte dans les images du fichier choisi, sans rien débiter. Une
 * analyse qui échoue ne bloque jamais la traduction : `analyse` reste `null`
 * et l'option n'est simplement pas proposée.
 */
export function useAnalyseImages(file: File | null, active: boolean) {
  // Le résultat garde son fichier : changer de document invalide aussitôt
  // l'ancien résultat, sans attendre la réponse du nouveau.
  const [resultat, setResultat] = useState<{ file: File; analyse: AnalyseImages | null } | null>(null);

  useEffect(() => {
    if (!file || !active) return;
    const ctrl = new AbortController();
    // Appelé une fois le dépôt fini : seul son identifiant part.
    const envoyer = () => postAvecFichier(`${API_BASE}/api/translate/analyse`, file, file.name, () => {}, {
      headers: { 'X-API-Key': API_KEY, ...authHeader() },
      signal: ctrl.signal,
    });
    (async () => {
      let analyse: AnalyseImages | null = null;
      try {
        let res = await envoyer();
        if (res.status === 401 && await refreshAccessToken()) res = await envoyer();
        if (res.ok) analyse = await res.json();
      } catch { /* option non proposée */ }
      if (!ctrl.signal.aborted) setResultat({ file, analyse });
    })();
    return () => ctrl.abort();
  }, [file, active]);

  const aJour = !!file && active && resultat?.file === file;
  return {
    analyse: aJour ? resultat.analyse : null,
    enCours: !!file && active && !aJour,
  };
}
