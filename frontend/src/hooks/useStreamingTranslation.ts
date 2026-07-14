import { useState, useRef, useCallback } from 'react';

const API_KEY = import.meta.env.VITE_API_KEY || 'precis_frontend_secure_key_2026_xK9mP2vL';
const API_BASE = import.meta.env.VITE_API_BASE || '';

/** État d'une page dans le pipeline progressif. */
export type PageStatus =
  | 'waiting'      // pas encore commencée
  | 'extracting'   // extraction des objets
  | 'translating'  // traduction DeepSeek
  | 'rendering'    // reconstruction du PDF
  | 'done'         // page traduite, affichable
  | 'copied';      // hors sélection : copiée de l'original (déjà affichable)

export interface StreamingState {
  isTranslating: boolean;
  totalPages: number | null;
  /** Statut par numéro de page (1-basé). */
  pageStatuses: Record<number, PageStatus>;
  /** PDF partiel : pages 1..renderedUpTo déjà prêtes (mis à jour au fil de l'eau). */
  partialBlob: Blob | null;
  /** Plus grand numéro de page présent dans partialBlob. */
  renderedUpTo: number;
  /** Résultat final complet (quand terminé). */
  result: { blob: Blob; filename: string } | null;
  error: string | null;
}

const EMPTY: StreamingState = {
  isTranslating: false,
  totalPages: null,
  pageStatuses: {},
  partialBlob: null,
  renderedUpTo: 0,
  result: null,
  error: null,
};

export function useStreamingTranslation() {
  const [state, setState] = useState<StreamingState>(EMPTY);
  const esRef = useRef<EventSource | null>(null);
  const jobIdRef = useRef<string | null>(null);
  // Évite les fetch de partiel concurrents (une page peut terminer pendant
  // qu'on télécharge encore le partiel de la précédente).
  const fetchingRef = useRef(false);
  const pendingFetchRef = useRef(false);

  const cancel = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
    setState((s) => ({ ...s, isTranslating: false }));
  }, []);

  const fetchPartial = useCallback(async (upTo: number) => {
    const jobId = jobIdRef.current;
    if (!jobId) return;
    if (fetchingRef.current) {
      pendingFetchRef.current = true;      // coalescer : on refera après
      return;
    }
    fetchingRef.current = true;
    try {
      const res = await fetch(`${API_BASE}/api/translate/partial/${jobId}`, {
        headers: { 'X-API-Key': API_KEY },
      });
      if (res.ok) {
        const blob = await res.blob();
        setState((s) => ({
          ...s,
          partialBlob: blob,
          renderedUpTo: Math.max(s.renderedUpTo, upTo),
        }));
      }
    } catch {
      // Le partiel peut être momentanément indisponible (réécriture atomique).
    } finally {
      fetchingRef.current = false;
      if (pendingFetchRef.current) {
        pendingFetchRef.current = false;
        fetchPartial(upTo);
      }
    }
  }, []);

  const start = useCallback(
    (
      file: File,
      targetLang: string,
      pages: string = '',
      debug: boolean = false,
    ): Promise<{ blob: Blob; filename: string }> => {
      return new Promise(async (resolve, reject) => {
        setState({ ...EMPTY, isTranslating: true });
        jobIdRef.current = null;
        fetchingRef.current = false;
        pendingFetchRef.current = false;

        try {
          // `quality` et `format_options` ne sont plus envoyés : le moteur PDF v2
          // ne les lit pas (il préserve toujours la mise en page et n'accepte pas
          // de modèle alternatif). Le serveur garde des valeurs par défaut.
          const formData = new FormData();
          formData.append('file', file);
          formData.append('target_lang', targetLang);
          if (debug) formData.append('debug', '1');
          if (pages && pages.trim()) formData.append('pages', pages.trim());

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
          jobIdRef.current = job_id;

          const es = new EventSource(`${API_BASE}/api/translate/events/${job_id}`);
          esRef.current = es;

          es.onmessage = async (e) => {
            if (!e.data || e.data.startsWith(':')) return;
            let msg: Record<string, unknown>;
            try { msg = JSON.parse(e.data); } catch { return; }
            const type = msg.type as string;

            if (type === 'start') {
              const total = (msg.total as number) ?? null;
              setState((s) => {
                const statuses: Record<number, PageStatus> = {};
                if (total) for (let i = 1; i <= total; i++) statuses[i] = 'waiting';
                return { ...s, totalPages: total, pageStatuses: statuses };
              });
            } else if (type === 'page') {
              const page = msg.page as number;
              const status = msg.status as PageStatus;
              setState((s) => ({
                ...s,
                pageStatuses: { ...s.pageStatuses, [page]: status },
                totalPages: (msg.total as number) ?? s.totalPages,
              }));
              if (status === 'done' || status === 'copied') {
                fetchPartial(page);
              }
            } else if (type === 'done') {
              es.close();
              esRef.current = null;
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
                setState((s) => ({
                  ...s,
                  isTranslating: false,
                  partialBlob: blob,
                  result: { blob, filename },
                }));
                resolve({ blob, filename });
              } catch (dlErr) {
                const m = dlErr instanceof Error ? dlErr.message : 'Erreur de téléchargement';
                setState((s) => ({ ...s, isTranslating: false, error: m }));
                reject(new Error(m));
              }
            } else if (type === 'error') {
              es.close();
              esRef.current = null;
              const m = (msg.message as string) || 'Erreur de traduction';
              setState((s) => ({ ...s, isTranslating: false, error: m }));
              reject(new Error(m));
            }
          };

          es.onerror = () => {
            es.close();
            esRef.current = null;
            setState((s) => {
              // Une coupure APRÈS le done final n'est pas une erreur.
              if (!s.isTranslating) return s;
              return { ...s, isTranslating: false, error: 'Connexion au serveur perdue' };
            });
            reject(new Error('Connexion au serveur perdue'));
          };
        } catch (err) {
          const m = err instanceof Error ? err.message : 'Erreur inconnue';
          setState((s) => ({ ...s, isTranslating: false, error: m }));
          reject(new Error(m));
        }
      });
    },
    [fetchPartial],
  );

  const reset = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
    jobIdRef.current = null;
    setState(EMPTY);
  }, []);

  return { ...state, start, cancel, reset };
}
