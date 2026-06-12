import { useState } from 'react';
import type { FormatOptions } from '../components/upload/TranslationSection';

const API_KEY = import.meta.env.VITE_API_KEY || 'precis_frontend_secure_key_2026_xK9mP2vL';
const API_BASE = import.meta.env.VITE_API_BASE || '';

export interface TranslationResult {
  blob: Blob;
  filename: string;
}

export interface TranslationProgress {
  stage: 'upload' | 'extraction' | 'translation' | 'injection' | 'done' | 'error';
  percent: number;
  message: string;
}

const STAGE_LABELS: Record<string, string> = {
  upload: 'Téléversement du document',
  extraction: 'Extraction du contenu',
  translation: 'Traduction par IA',
  injection: 'Génération du document',
  done: 'Terminé',
  error: 'Erreur',
};

export function stageLabel(stage: string): string {
  return STAGE_LABELS[stage] || stage;
}

/** Lit le flux SSE de progression d'un job (fetch streaming : EventSource ne
 * permet pas l'en-tête X-API-Key). Résout sur 'done', rejette sur 'error'. */
async function streamProgress(
  jobId: string,
  onEvent: (ev: TranslationProgress) => void
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/translate/${jobId}/events`, {
    headers: { 'X-API-Key': API_KEY },
  });

  if (!res.ok || !res.body) {
    // Repli : polling du résultat (RNF-5)
    await pollUntilDone(jobId, onEvent);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });

    let idx: number;
    while ((idx = buf.indexOf('\n\n')) >= 0) {
      const raw = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const dataLine = raw.split('\n').find((l) => l.startsWith('data: '));
      if (!dataLine) continue;
      try {
        const ev = JSON.parse(dataLine.slice(6)) as TranslationProgress;
        onEvent(ev);
        if (ev.stage === 'error') throw new Error(ev.message || 'Erreur de traduction');
        if (ev.stage === 'done') return;
      } catch (e) {
        if (e instanceof Error && e.message !== 'Unexpected end of JSON input') throw e;
      }
    }
  }
}

/** Repli sans SSE : interroge le résultat jusqu'à disponibilité (425 = en cours). */
async function pollUntilDone(
  jobId: string,
  onEvent: (ev: TranslationProgress) => void
): Promise<void> {
  const deadline = Date.now() + 10 * 60 * 1000;
  let fakePercent = 10;
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 1500));
    const res = await fetch(`${API_BASE}/api/translate/${jobId}/result`, {
      method: 'HEAD',
      headers: { 'X-API-Key': API_KEY },
    });
    if (res.status === 425) {
      fakePercent = Math.min(fakePercent + 4, 95);
      onEvent({ stage: 'translation', percent: fakePercent, message: 'Traduction en cours…' });
      continue;
    }
    if (res.ok || res.status === 405) return; // prêt (405 : HEAD non géré → prêt)
    throw new Error(`Échec de la traduction (HTTP ${res.status})`);
  }
  throw new Error('Délai de traduction dépassé.');
}

export function useTranslation() {
  const [isTranslating, setIsTranslating] = useState(false);
  const [progress, setProgress] = useState<TranslationProgress | null>(null);
  const [error, setError] = useState<string | null>(null);

  const translateFile = async (
    file: File,
    targetLang: string,
    formatOptions?: FormatOptions
  ): Promise<TranslationResult> => {
    setIsTranslating(true);
    setError(null);
    setProgress({ stage: 'upload', percent: 2, message: 'Téléversement du document…' });

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('target_lang', targetLang);
      if (formatOptions) {
        formData.append('format_options', JSON.stringify(formatOptions));
      }

      const response = await fetch(`${API_BASE}/api/translate`, {
        method: 'POST',
        headers: { 'X-API-Key': API_KEY },
        body: formData,
      });

      let blob: Blob;

      if (response.status === 202) {
        // Mode asynchrone : suivi de progression temps réel puis récupération
        const { job_id } = await response.json();
        await streamProgress(job_id, setProgress);

        const fileRes = await fetch(`${API_BASE}/api/translate/${job_id}/result`, {
          headers: { 'X-API-Key': API_KEY },
        });
        if (!fileRes.ok) {
          const errorData = await fileRes.json().catch(() => ({} as any));
          throw new Error(errorData.detail || 'Échec de la récupération du document traduit');
        }
        blob = await fileRes.blob();
      } else if (response.ok) {
        // Mode synchrone (compatibilité backend antérieur)
        blob = await response.blob();
      } else {
        const errorData = await response.json().catch(() => ({} as any));
        throw new Error(errorData.detail || errorData.error || 'Translation failed');
      }

      const filename =
        file.name.replace(/\.[^/.]+$/, '') + '_TRADUIT.' + file.name.split('.').pop();

      setProgress({ stage: 'done', percent: 100, message: 'Traduction terminée.' });
      return { blob, filename };
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      setProgress({ stage: 'error', percent: 0, message });
      throw err;
    } finally {
      setIsTranslating(false);
    }
  };

  return { translateFile, isTranslating, progress, error };
}
