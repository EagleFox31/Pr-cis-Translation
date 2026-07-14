import { useState, useCallback, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import api from '../services/api';

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

  /** Récupérer le blob d'un document. Connecté = download API, Visiteur = mémoire. */
  const getBlob = useCallback(async (id: string): Promise<Blob | undefined> => {
    if (user) {
      const res = await api.get(`/api/documents/${id}/download`);
      if (res.ok && res.data instanceof Blob) return res.data;
      // Si la réponse n'est pas un blob, on tente un fetch direct
      const API_BASE = (import.meta as any).env?.VITE_API_BASE || '';
      const tokens = JSON.parse(localStorage.getItem('precis_tokens') || '{}');
      const fetchRes = await fetch(`${API_BASE}/api/documents/${id}/download`, {
        headers: tokens.access_token ? { Authorization: `Bearer ${tokens.access_token}` } : {},
      });
      if (fetchRes.ok) return fetchRes.blob();
      return undefined;
    }
    return documents.find(d => d.id === id)?._blob;
  }, [user, documents]);

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

  return { documents, loading, saveDocument, getBlob, deleteDocument, clearAll };
}
