import { useState, useCallback, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import api, { authFetch } from '../services/api';

export interface DocMeta {
  id: string;
  filename: string;
  originalName: string;
  targetLang: string;
  date: string;
  sizeByes: number;
  ext: string;
  /** blob dispo uniquement pour les visiteurs (en mémoire) */
  _blob?: Blob;
}

const LS_LEGACY = 'precis_doc_library';

/**
 * Bibliothèque de documents.
 *
 * - Visiteur (non connecté) : stockage mémoire uniquement, rien n'est persisté.
 *   Fermer l'onglet = tout est perdu.
 * - Connecté : documents chargés depuis /api/documents, téléchargement via
 *   /api/documents/{id}/download. Pas de localStorage, pas d'IndexedDB.
 */
export function useDocumentLibrary() {
  const { user } = useAuth();
  const [documents, setDocuments] = useState<DocMeta[]>([]);
  const [loading, setLoading] = useState(false);

  // Nettoyer les anciennes données localStorage au montage
  useEffect(() => {
    try { localStorage.removeItem(LS_LEGACY); } catch { /* ignore */ }
  }, []);

  // Connecté → charger depuis l'API
  useEffect(() => {
    if (!user) return;
    (async () => {
      setLoading(true);
      const res = await api.get('/api/documents');
      if (res.ok) {
        const docs = (res.data as any[]).map((d: any) => ({
          id: d.id,
          filename: d.original_name,
          originalName: d.original_name,
          targetLang: d.target_lang,
          date: d.created_at,
          sizeByes: d.size_bytes,
          ext: d.original_name.split('.').pop()?.toLowerCase() ?? 'pdf',
          _blob: undefined,
        }));
        setDocuments(docs);
      }
      setLoading(false);
    })();
  }, [user]);

  /** Ajouter un document (blob + meta). Visiteur = mémoire, Connecté = déjà fait côté backend. */
  const saveDocument = useCallback(async (
    blob: Blob, filename: string,
    meta: Omit<DocMeta, 'id' | 'date' | 'sizeByes' | 'filename' | '_blob'>,
  ): Promise<string> => {
    const id = crypto.randomUUID();
    const doc: DocMeta = {
      ...meta, id, filename,
      date: new Date().toISOString(),
      sizeByes: blob.size,
      _blob: blob,
    };
    if (user) {
      // Pour les connectés, le blob est déjà sauvegardé côté backend
      // lors de la traduction. On recharge la liste.
      const res = await api.get('/api/documents');
      if (res.ok) {
        const docs = (res.data as any[]).map((d: any) => ({
          id: d.id, filename: d.original_name, originalName: d.original_name,
          targetLang: d.target_lang, date: d.created_at, sizeByes: d.size_bytes,
          ext: d.original_name.split('.').pop()?.toLowerCase() ?? 'pdf',
          _blob: undefined,
        }));
        setDocuments(docs);
      }
      return id;
    }
    setDocuments(prev => [doc, ...prev]);
    return id;
  }, [user]);

  /** Récupérer le blob d'un document. Connecté = download API, Visiteur = mémoire.
   *
   *  `authFetch` et pas `api.get` : ce dernier fait `res.json()` et ne peut donc
   *  JAMAIS rendre un blob (`res.data instanceof Blob` était toujours faux, le
   *  premier appel était perdu à chaque fois). Le repli lisait le token dans
   *  `localStorage` — donc l'ANCIEN après un refresh, d'où des 401 sur une
   *  session pourtant valide. `authFetch` prend le token en mémoire et rejoue
   *  l'appel après refresh. */
  const getBlob = useCallback(async (id: string): Promise<Blob | undefined> => {
    if (user) {
      const res = await authFetch(`/api/documents/${id}/download`);
      return res.ok ? res.blob() : undefined;
    }
    return documents.find(d => d.id === id)?._blob;
  }, [user, documents]);

  /** Blob d'AFFICHAGE : passe par /preview, qui rastérise et filigrane pour un
   *  plan d'essai. « Aperçu » ne doit jamais emprunter /download — c'est par là
   *  qu'un compte gratuit récupérait sa traduction en clair. */
  const getPreviewBlob = useCallback(async (id: string): Promise<Blob | undefined> => {
    if (user) {
      const res = await authFetch(`/api/documents/${id}/preview`);
      return res.ok ? res.blob() : undefined;
    }
    return documents.find(d => d.id === id)?._blob;
  }, [user, documents]);

  /** Le fichier SOURCE tel que déposé — panneau gauche de l'aperçu.
   *  `/download` rend la traduction dès qu'elle existe : il ne peut pas servir
   *  à ça. Sans cette route, le viewer n'avait pas de source et affichait le
   *  PDF de DÉMO à côté du document de l'utilisateur. */
  const getOriginalBlob = useCallback(async (id: string): Promise<Blob | undefined> => {
    if (user) {
      const res = await authFetch(`/api/documents/${id}/original`);
      return res.ok ? res.blob() : undefined;
    }
    return undefined;
  }, [user]);

  const deleteDocument = useCallback(async (id: string) => {
    if (user) {
      await api.delete(`/api/documents/${id}`);
      setDocuments(prev => prev.filter(d => d.id !== id));
      return;
    }
    setDocuments(prev => prev.filter(d => d.id !== id));
  }, [user]);

  const clearAll = useCallback(async () => {
    if (user) {
      for (const d of documents) await api.delete(`/api/documents/${d.id}`);
    }
    setDocuments([]);
  }, [user, documents]);

  return { documents, loading, saveDocument, getBlob, getPreviewBlob,
           getOriginalBlob, deleteDocument, clearAll };
}
