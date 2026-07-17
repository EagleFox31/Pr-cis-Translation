import { useState, useEffect } from 'react';
import { authHeader } from '../services/api';

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
    throw new Error(err.detail || 'Conversion PDF pour l’aperçu échouée');
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
 * via pdf.js. Les PDF passent sans conversion. Ne se relance que si les blobs ou
 * le format changent — pas sur le zoom/la pagination.
 */
export function usePdfPreview(
  source: Blob | null | undefined,
  translated: Blob | null | undefined,
  ext: string,
): PdfPreviewState {
  const [state, setState] = useState<PdfPreviewState>({
    sourcePdf: null,
    translatedPdf: null,
    loading: false,
    error: null,
  });

  useEffect(() => {
    let active = true;

    // Rien à afficher.
    if (!source && !translated) {
      setState({ sourcePdf: null, translatedPdf: null, loading: false, error: null });
      return;
    }

    // PDF natif : aucun appel réseau.
    if (ext === 'pdf') {
      setState({
        sourcePdf: source ?? null,
        translatedPdf: translated ?? null,
        loading: false,
        error: null,
      });
      return;
    }

    setState((s) => ({ ...s, loading: true, error: null }));

    (async () => {
      try {
        const [sourcePdf, translatedPdf] = await Promise.all([
          source ? convertToPdf(source, ext) : Promise.resolve(null),
          translated ? convertToPdf(translated, ext) : Promise.resolve(null),
        ]);
        if (!active) return;
        setState({ sourcePdf, translatedPdf, loading: false, error: null });
      } catch (err) {
        if (!active) return;
        const message = err instanceof Error ? err.message : 'Erreur de conversion';
        setState({ sourcePdf: null, translatedPdf: null, loading: false, error: message });
      }
    })();

    return () => {
      active = false;
    };
  }, [source, translated, ext]);

  return state;
}
