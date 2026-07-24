import { useState, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { authHeader, accessToken } from '../services/api';
import i18n from '../i18n';

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
  /** L'erreur vient d'un 402 (limite de forfait atteinte) → afficher un CTA. */
  limitReached: boolean;
  /** En file d'attente : aucun worker libre. `null` = pas en file (démarré ou
   *  terminé). Le nombre est une estimation des demandes devant la vôtre. */
  queuePosition: number | null;
}

const EMPTY: StreamingState = {
  isTranslating: false,
  totalPages: null,
  pageStatuses: {},
  partialBlob: null,
  renderedUpTo: 0,
  result: null,
  error: null,
  limitReached: false,
  queuePosition: null,
};

export function useStreamingTranslation() {
  const { t } = useTranslation();
  const [state, setState] = useState<StreamingState>(EMPTY);
  const esRef = useRef<EventSource | null>(null);
  const jobIdRef = useRef<string | null>(null);
  // Évite les fetch de partiel concurrents (une page peut terminer pendant
  // qu'on télécharge encore le partiel de la précédente).
  const fetchingRef = useRef(false);
  const pendingFetchRef = useRef(false);
  // Dernier partiel reçu. En essai, /result est refusé (402) : c'est lui qui
  // fait office de résultat. Un ref, pas un state : on le lit dans le
  // gestionnaire SSE, hors du cycle de rendu.
  const lastPartialRef = useRef<Blob | null>(null);

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
        headers: { 'X-API-Key': API_KEY, ...authHeader() },
      });
      if (res.ok) {
        const blob = await res.blob();
        lastPartialRef.current = blob;   // repli si /result est refusé (essai)
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
      precise: boolean = false,
    ): Promise<{ blob: Blob; filename: string }> => {
      return new Promise(async (resolve, reject) => {
        // Fermer TOUT flux encore ouvert avant d'en démarrer un nouveau. Relancer
        // une traduction alors qu'une était en cours (ou quittée par Retour)
        // laissait l'ancien `EventSource` ouvert : une connexion fuitée, et ses
        // événements `page`/`partial` qui venaient se mélanger à ceux du nouveau
        // job. L'ancien job continue côté serveur et reste dans la bibliothèque
        // (voulu) ; seul son SUIVI est abandonné proprement.
        esRef.current?.close();
        esRef.current = null;

        setState({ ...EMPTY, isTranslating: true });
        // Sans ça, un 402 survenant avant le premier partiel du NOUVEAU
        // document résoudrait avec celui du PRÉCÉDENT — on afficherait le
        // mauvais document sans que rien ne signale l'erreur.
        lastPartialRef.current = null;
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
          if (precise) formData.append('precise', '1');
          if (pages && pages.trim()) formData.append('pages', pages.trim());

          // `authHeader()` est INDISPENSABLE ici, pas décoratif : le backend lit
          // l'utilisateur via `optional_auth`. Sans token il voit un visiteur
          // anonyme, n'enregistre AUCUN `Document` (la bibliothèque reste vide)
          // et n'applique pas le quota freemium. Un visiteur envoie `{}` et
          // reste anonyme, comme avant.
          const startRes = await fetch(`${API_BASE}/api/translate`, {
            method: 'POST',
            headers: { 'X-API-Key': API_KEY, ...authHeader() },
            body: formData,
          });
          if (!startRes.ok) {
            const err = await startRes.json().catch(() => ({}));
            const detail = err.detail || err.error || t('story.error_default');
            const is402 = startRes.status === 402;
            setState((s) => ({ ...s, isTranslating: false, error: detail, limitReached: is402 }));
            throw new Error(detail);
          }
          const { job_id } = await startRes.json();
          jobIdRef.current = job_id;

          // Le JWT passe en query : EventSource ne porte pas de header, et le
          // backend n'accepte plus un flux anonyme (la file d'événements est à
          // consommateur unique — un tiers la viderait).
          const es = new EventSource(
            `${API_BASE}/api/translate/events/${job_id}?token=${encodeURIComponent(accessToken() ?? '')}`,
          );
          esRef.current = es;

          es.onmessage = async (e) => {
            if (!e.data || e.data.startsWith(':')) return;
            let msg: Record<string, unknown>;
            try { msg = JSON.parse(e.data); } catch { return; }
            const type = msg.type as string;

            if (type === 'queued') {
              // Aucun worker libre : le job attend son tour dans la file de
              // priorité. On l'affiche sans rien changer d'autre.
              const ahead = (msg.ahead as number) ?? 0;
              setState((s) => ({ ...s, queuePosition: ahead }));
              return;
            }
            // Tout autre événement veut dire que le job a QUITTÉ la file (un
            // worker l'a pris) : on efface l'état d'attente une bonne fois.
            setState((s) => (s.queuePosition === null ? s : { ...s, queuePosition: null }));

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
            } else if (type === 'partial') {
              // PPTX PROGRESSIF : le backend signale qu'un nouveau PDF partiel
              // est PRÊT à être récupéré — d'abord le SOCLE (le document
              // d'origine, `pages: 0`), puis chaque lot de diapositives
              // greffées. C'est LE signal d'affichage progressif.
              //
              // Sans ce handler, l'aperçu ne se rafraîchissait que sur les
              // événements `page`. En traduction IA (lente), ça suffisait par
              // hasard : les `page` s'espaçaient assez pour laisser le partiel
              // se préparer. Mais en mode STRUCTURE (sans IA), toutes les pages
              // « terminent » en quelques millisecondes — AVANT que LibreOffice
              // ait converti la moindre diapositive. Les `fetchPartial` de ces
              // `page` tombaient dans le vide, et les partiels réellement prêts
              // (émis APRÈS, en `partial`) étaient ignorés : on ne voyait donc
              // RIEN jusqu'à la fin. En écoutant `partial`, l'original apparaît
              // dès que le socle est prêt, puis l'aperçu se remplit au rythme
              // réel des conversions — quelle que soit la vitesse de traduction.
              fetchPartial((msg.pages as number) ?? 0);
            } else if (type === 'done') {
              es.close();
              esRef.current = null;
              try {
                const dlRes = await fetch(`${API_BASE}/api/translate/result/${job_id}`, {
                  headers: { 'X-API-Key': API_KEY, ...authHeader() },
                });
                const filename = (msg.filename as string) ||
                  file.name.replace(/\.[^/.]+$/, '') + '_TRADUIT.' + file.name.split('.').pop();

                // 402 = le FORFAIT parle, ce n'est pas une panne. Un plan
                // d'essai n'a pas droit au résultat téléchargeable ; il a droit
                // à l'aperçu (partiel rastérisé et filigrané). Traiter ce refus
                // comme une erreur laissait la traduction bloquée sur « page en
                // attente » alors qu'elle avait parfaitement abouti.
                //
                // On REDEMANDE le partiel ICI, maintenant qu'il est GARANTI
                // complet côté serveur. Indispensable pour le PPTX : son partiel
                // est converti en PDF de façon asynchrone (LibreOffice, ~10 s) et
                // n'était souvent pas encore prêt au dernier événement `page` —
                // `lastPartialRef` restait alors vide et l'essai voyait une
                // erreur au lieu de son aperçu.
                if (dlRes.status === 402) {
                  let blob = lastPartialRef.current;
                  try {
                    const pr = await fetch(`${API_BASE}/api/translate/partial/${job_id}`, {
                      headers: { 'X-API-Key': API_KEY, ...authHeader() },
                    });
                    if (pr.ok) blob = await pr.blob();
                  } catch {
                    // réseau : on se rabat sur le dernier partiel connu
                  }
                  if (blob) {
                    setState((s) => ({ ...s, isTranslating: false, partialBlob: blob, result: { blob, filename } }));
                    resolve({ blob, filename });
                    return;
                  }
                }
                if (!dlRes.ok) {
                  const err = await dlRes.json().catch(() => ({}));
                  throw new Error(err.detail || i18n.t('common.download_failed'));
                }
                const blob = await dlRes.blob();
                setState((s) => ({
                  ...s,
                  isTranslating: false,
                  partialBlob: blob,
                  result: { blob, filename },
                }));
                resolve({ blob, filename });
              } catch (dlErr) {
                const m = dlErr instanceof Error ? dlErr.message : t('story.error_translation_failed');
                setState((s) => ({ ...s, isTranslating: false, error: m }));
                reject(new Error(m));
              }
            } else if (type === 'error') {
              es.close();
              esRef.current = null;
              const m = (msg.message as string) || t('story.error_translation_failed');
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
              return { ...s, isTranslating: false, error: t('story.error_connection_lost') };
            });
            reject(new Error(t('story.error_connection_lost')));
          };
        } catch (err) {
          const m = err instanceof Error ? err.message : t('story.error_unknown');
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
    lastPartialRef.current = null;
    setState(EMPTY);
  }, []);

  return { ...state, start, cancel, reset };
}
