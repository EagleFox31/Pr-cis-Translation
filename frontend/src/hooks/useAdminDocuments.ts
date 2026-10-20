/**
 * Données de la console d'administration des documents (`/admin/documents`).
 *
 * Lecture seule : l'admin retrouve le document d'un utilisateur et en télécharge
 * l'original comme la traduction pour reproduire un rendu cassé. La recherche
 * (e-mail du propriétaire ou nom de fichier) est différée de 300 ms pour ne pas
 * interroger le serveur à chaque frappe.
 */
import { useCallback, useEffect, useState } from 'react';
import { authFetch } from '../services/api';
import api from '../services/api';

export interface AdminDocument {
  id: string;
  original_name: string;
  user_email: string | null;
  source_lang: string;
  target_lang: string;
  status: string;
  page_count: number | null;
  size_bytes: number;
  created_at: string | null;
  has_original: boolean;
  has_translation: boolean;
}

export type AdminDocKind = 'original' | 'translated';

const DEBOUNCE_MS = 300;

/** Nom de fichier annoncé par le serveur (`filename*=UTF-8''…`), sinon repli. */
function filenameFrom(res: Response, fallback: string): string {
  const cd = res.headers.get('Content-Disposition') || '';
  const m = /filename\*=UTF-8''([^;]+)/i.exec(cd);
  if (m) {
    try { return decodeURIComponent(m[1]); } catch { /* repli ci-dessous */ }
  }
  return fallback;
}

export function useAdminDocuments() {
  const [q, setQ] = useState('');
  const [debouncedQ, setDebouncedQ] = useState('');
  const [items, setItems] = useState<AdminDocument[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const id = setTimeout(() => setDebouncedQ(q.trim()), DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [q]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    const query = debouncedQ ? `?q=${encodeURIComponent(debouncedQ)}` : '';
    const res = await api.get(`/api/admin/documents${query}`);
    if (res.ok && res.data) {
      const d = res.data as { items: AdminDocument[]; total: number };
      setItems(d.items || []);
      setTotal(d.total || 0);
    } else {
      setError(String(res.status));
    }
    setLoading(false);
  }, [debouncedQ]);

  useEffect(() => { void refresh(); }, [refresh]);

  /** Télécharge l'original ou la traduction d'un document (fetch authentifié
   *  puis lien `a.download`). Renvoie le statut HTTP pour le message d'erreur. */
  const download = useCallback(
    async (doc: AdminDocument, kind: AdminDocKind): Promise<{ ok: boolean; status: number }> => {
      const res = await authFetch(`/api/admin/documents/${encodeURIComponent(doc.id)}/${kind}`);
      if (!res.ok) return { ok: false, status: res.status };
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filenameFrom(res, doc.original_name);
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
      return { ok: true, status: res.status };
    },
    [],
  );

  return { q, setQ, items, total, loading, error, refresh, download };
}
