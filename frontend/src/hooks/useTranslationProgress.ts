import { useState, useRef, useCallback } from 'react';
import type { FormatOptions } from '../components/upload/TranslationSection';

const API_KEY = import.meta.env.VITE_API_KEY || 'precis_frontend_secure_key_2026_xK9mP2vL';
const API_BASE = import.meta.env.VITE_API_BASE || '';

export type ProgressStep = 'idle' | 'start' | 'extract' | 'translate' | 'inject' | 'cache' | 'done' | 'error';

export interface ProgressEvent {
  step: ProgressStep;
  message: string;
  page: number | null;
  total: number | null;
}

export interface TranslationProgressResult {
  blob: Blob;
  filename: string;
}

export function useTranslationProgress() {
  const [isTranslating, setIsTranslating] = useState(false);
  const [progress, setProgress] = useState<ProgressEvent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  const cancel = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
    setIsTranslating(false);
    setProgress(null);
  }, []);

  const translateFile = useCallback(
    (file: File, targetLang: string, formatOptions?: FormatOptions, quality: string = 'fast', pages: string = ''): Promise<TranslationProgressResult> => {
      return new Promise(async (resolve, reject) => {
        setIsTranslating(true);
        setError(null);
        setProgress({ step: 'start', message: 'Envoi du fichier...', page: null, total: null });

        try {
          // 1. POST → obtenir job_id
          const formData = new FormData();
          formData.append('file', file);
          formData.append('target_lang', targetLang);
          formData.append('quality', quality);
          if (pages && pages.trim()) formData.append('pages', pages.trim());
          if (formatOptions) formData.append('format_options', JSON.stringify(formatOptions));

          const startRes = await fetch(`${API_BASE}/api/translate`, {
            method: 'POST',
            headers: { 'X-API-Key': API_KEY },
            body: formData,
          });

          if (!startRes.ok) {
            const err = await startRes.json().catch(() => ({}));
            throw new Error(err.detail || err.error || 'Démarrage de la traduction échoué');
          }

          const { job_id } = await startRes.json();

          // 2. SSE progress stream
          const es = new EventSource(
            `${API_BASE}/api/translate/events/${job_id}`,
          );
          // EventSource ne supporte pas les headers custom nativement —
          // le backend accepte le job_id dans l'URL donc pas d'auth sur le SSE
          // (même domaine ; pour production mettre un token à durée de vie courte).
          esRef.current = es;

          es.onmessage = async (e) => {
            if (!e.data || e.data.startsWith(':')) return;
            let msg: Record<string, unknown>;
            try { msg = JSON.parse(e.data); } catch { return; }

            const type = msg.type as string;

            if (type === 'progress') {
              setProgress({
                step: (msg.step as ProgressStep) ?? 'start',
                message: (msg.message as string) ?? '',
                page: (msg.page as number | null) ?? null,
                total: (msg.total as number | null) ?? null,
              });
            } else if (type === 'done') {
              es.close();
              esRef.current = null;

              // 3. Télécharger le résultat
              try {
                const dlRes = await fetch(`${API_BASE}/api/translate/result/${job_id}`, {
                  headers: { 'X-API-Key': API_KEY },
                });
                if (!dlRes.ok) {
                  const err = await dlRes.json().catch(() => ({}));
                  throw new Error(err.detail || 'Téléchargement du résultat échoué');
                }
                const blob = await dlRes.blob();
                const filename = (msg.filename as string) ||
                  file.name.replace(/\.[^/.]+$/, '') + '_TRADUIT.' + file.name.split('.').pop();

                setProgress({ step: 'done', message: 'Traduction terminée !', page: null, total: null });
                setIsTranslating(false);
                resolve({ blob, filename });
              } catch (dlErr) {
                const message = dlErr instanceof Error ? dlErr.message : 'Erreur de téléchargement';
                setError(message);
                setIsTranslating(false);
                reject(new Error(message));
              }
            } else if (type === 'error') {
              es.close();
              esRef.current = null;
              const message = (msg.message as string) || 'Erreur de traduction';
              setError(message);
              setIsTranslating(false);
              reject(new Error(message));
            }
          };

          es.onerror = () => {
            es.close();
            esRef.current = null;
            const message = 'Connexion au serveur perdue';
            setError(message);
            setIsTranslating(false);
            reject(new Error(message));
          };
        } catch (err) {
          const message = err instanceof Error ? err.message : 'Erreur inconnue';
          setError(message);
          setIsTranslating(false);
          reject(new Error(message));
        }
      });
    },
    [],
  );

  return { translateFile, isTranslating, progress, error, cancel };
}
