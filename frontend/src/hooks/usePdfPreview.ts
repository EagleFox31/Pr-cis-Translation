import { useState, useEffect, useRef } from 'react';
import { authHeader } from '../services/api';
import i18n from '../i18n';

const API_KEY = import.meta.env.VITE_API_KEY || 'precis_frontend_secure_key_2026_xK9mP2vL';
const API_BASE = import.meta.env.VITE_API_BASE || '';

async function convertToPdf(data: Blob, ext: string): Promise<Blob> {
  // Déjà un PDF → rien à convertir.
  if (ext === 'pdf') return data;

  const form = new FormData();
  // Le backend déduit le format depuis l'extension du nom de fichier.
  form.append('file', data, `preview.${ext}`);

  // `authHeader()` obligatoire : le backend exige désormais une session pour
  // convertir (la clé d'API est publique, elle ne protège rien à elle seule).
  const res = await fetch(`${API_BASE}/api/preview/pdf`, {
    method: 'POST',
    headers: { 'X-API-Key': API_KEY, ...authHeader() },
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Conversion PDF pour l\u2019aperçu échouée');
  }
  return res.blob();
}

interface PdfPreviewState {
  sourcePdf: Blob | null;
  translatedPdf: Blob | null;
  loading: boolean;
  error: string | null;
}

/**
 * Convertit (si besoin) l'original et la traduction en PDF pour un aperçu exact
 * via pdf.js. Les PDF passent sans conversion.
 *
 * DEUX effets séparés : la source et la traduction sont indépendants.
 *
 *  • La SOURCE ne change pas quand on tourne les pages d'un aperçu
 *    bibliothèque — elle est convertie UNE FOIS et cachée via un ref.
 *    `loading` ne bloque les deux panneaux que pendant cette première
 *    conversion ; ensuite, le panneau source reste visible en permanence.
 *
 *  • La TRADUCTION change à chaque page. Quand elle est en cours de
 *    conversion, `translatedPdf` est null et PdfViewer affiche son
 *    placeholder avec spinner — le panneau source ne bouge pas.
 *
 * @param translatedExt Extension du blob traduit. Si absente, utilise `ext`.
 *   Utile pour le streaming PPTX : le blob traduit (partial) est déjà un PDF
 *   converti par le backend, seul l'original a besoin de conversion.
 */
export function usePdfPreview(
  source: Blob | null | undefined,
  translated: Blob | null | undefined,
  ext: string,
  translatedExt?: string,
): PdfPreviewState {
  const tgtExt = translatedExt ?? ext;

  // ── Source ──────────────────────────────────────────────────────────────
  const [sourcePdf, setSourcePdf] = useState<Blob | null>(null);
  const [sourceLoading, setSourceLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Cache : on ne reconvertit que si le blob SOURCE a changé (identité).
  // Un ref plutôt qu'un state : changer le cache ne doit pas relancer
  // l'effet — c'est l'effet qui le remplit, pas l'inverse.
  const sourceCacheRef = useRef<{ blob: Blob; pdf: Blob } | null>(null);

  useEffect(() => {
    let active = true;

    if (!source) {
      setSourcePdf(null);
      setSourceLoading(false);
      sourceCacheRef.current = null;
      return;
    }

    // PDF natif : aucun appel réseau.
    if (ext === 'pdf') {
      setSourcePdf(source);
      setSourceLoading(false);
      return;
    }

    // Même blob qu'au dernier appel → résultat en cache.
    if (sourceCacheRef.current && sourceCacheRef.current.blob === source) {
      setSourcePdf(sourceCacheRef.current.pdf);
      setSourceLoading(false);
      return;
    }

    // Conversion nécessaire : bloque les deux panneaux (première ouverture).
    setSourceLoading(true);
    setError(null);

    convertToPdf(source, ext)
      .then((pdf) => {
        if (!active) return;
        sourceCacheRef.current = { blob: source, pdf };
        setSourcePdf(pdf);
        setSourceLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        setSourcePdf(null);
        setSourceLoading(false);
        setError(err instanceof Error ? err.message : 'Erreur de conversion source');
      });

    return () => { active = false; };
  }, [source, ext]);

  // ── Traduction ─────────────────────────────────────────────────────────
  const [translatedPdf, setTranslatedPdf] = useState<Blob | null>(null);

  useEffect(() => {
    let active = true;

    if (!translated) {
      setTranslatedPdf(null);
      return;
    }

    // PDF natif : pas de conversion.
    if (tgtExt === 'pdf') {
      setTranslatedPdf(translated);
      return;
    }

    // Conversion : on ne bloque PAS les deux panneaux (`loading` reste à
    // false si la source est déjà prête). PdfViewer montre son placeholder
    // « page en cours de rendu » le temps que la conversion finisse.
    setTranslatedPdf(null);     // panneau traduit → placeholder spinner
    setError(null);

    convertToPdf(translated, tgtExt)
      .then((pdf) => {
        if (!active) return;
        setTranslatedPdf(pdf);
      })
      .catch((err) => {
        if (!active) return;
        setTranslatedPdf(null);
        setError(err instanceof Error ? err.message : 'Erreur de conversion traduction');
      });

    return () => { active = false; };
  }, [translated, tgtExt]);

  // `loading` ne vaut true que quand la SOURCE n'est pas prête : c'est le
  // seul cas où les deux panneaux sont masqués (spinner plein écran).
  // Quand la source est prête et la traduction en cours, PdfViewer affiche
  // le panneau source + un placeholder dans le panneau traduit.
  return { sourcePdf, translatedPdf, loading: sourceLoading, error };
}
