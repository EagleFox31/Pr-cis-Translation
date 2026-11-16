/**
 * Données de la console d'administration des documents (`/admin/documents`).
 *
 * L'admin retrouve le document d'un utilisateur, en télécharge l'original comme
 * la traduction pour reproduire un rendu cassé, ou l'ouvre dans l'aperçu de l'accueil. La recherche
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
  /** Identifiant du document client dont celui-ci est une copie d'admin. */
  copie_de: string | null;
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

/** Télécharge l'original ou la traduction d'un document (fetch authentifié
 *  puis lien `a.download`). Renvoie le statut HTTP pour le message d'erreur. */
export async function downloadAdminDocument(
  id: string, kind: AdminDocKind, fallbackName: string,
): Promise<{ ok: boolean; status: number }> {
  const res = await authFetch(`/api/admin/documents/${encodeURIComponent(id)}/${kind}`);
  if (!res.ok) return { ok: false, status: res.status };
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filenameFrom(res, fallbackName);
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
  return { ok: true, status: res.status };
}

/** Message d'erreur du serveur (`detail`), sinon le code HTTP. */
async function detailOf(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (body && typeof body.detail === 'string') return body.detail;
  } catch { /* corps absent ou illisible */ }
  return String(res.status);
}

/** PDF de l'original (`source`) ou de la traduction rendue (`apercu`), pour
 *  l'aperçu de l'accueil. Lève une `Error` portant le message du serveur. */
export async function fetchAdminPdf(
  id: string, kind: 'source' | 'apercu',
): Promise<Blob> {
  const route = kind === 'source' ? 'source-pdf' : 'apercu';
  const res = await authFetch(`/api/admin/documents/${encodeURIComponent(id)}/${route}`);
  if (!res.ok) throw new Error(await detailOf(res));
  return res.blob();
}

/** Crée, au nom de l'admin, une copie du document d'un client (photo de sa
 *  traduction). `cree: false` = la copie existait déjà. */
export async function createAdminCopy(
  id: string,
): Promise<{ id: string; cree: boolean }> {
  const res = await authFetch(
    `/api/admin/documents/${encodeURIComponent(id)}/copie`, { method: 'POST' });
  if (!res.ok) throw new Error(await detailOf(res));
  return res.json();
}

/** La recherche `q` est fournie par la page (elle vit dans l'adresse). */
export function useAdminDocuments(q: string) {
  const [debouncedQ, setDebouncedQ] = useState(q.trim());
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

  return {
    items, total, loading, error, refresh,
    download: (doc: AdminDocument, kind: AdminDocKind) =>
      downloadAdminDocument(doc.id, kind, doc.original_name),
  };
}
