/**
 * Données de la page d'administration du journal d'erreurs.
 *
 * Regroupe les appels admin (`/api/logs/*`) en une surface simple : la liste
 * groupée, le détail d'un groupe, et les trois actions du cycle « consigner puis
 * vider » — exporter, marquer traité, supprimer.
 */
import { useCallback, useEffect, useState } from 'react';
import api, { authFetch } from '../services/api';

export interface LogGroup {
  fingerprint: string;
  source: string;
  level: string;
  message: string;
  count: number;
  new_count: number;
  status: 'new' | 'handled';
  last_seen: string | null;
  first_seen: string | null;
}

export interface LogOccurrence {
  id: string;
  source: string;
  level: string;
  message: string;
  stack: string | null;
  context: Record<string, unknown> | null;
  user_email: string | null;
  fingerprint: string;
  status: string;
  handled_at: string | null;
  created_at: string | null;
}

export interface LogFilters {
  source?: string;
  level?: string;
  status?: string;
  q?: string;
}

function buildQuery(f: LogFilters): string {
  const p = new URLSearchParams();
  if (f.source) p.set('source', f.source);
  if (f.level) p.set('level', f.level);
  if (f.status) p.set('status', f.status);
  if (f.q) p.set('q', f.q);
  const s = p.toString();
  return s ? `?${s}` : '';
}

export function useErrorLogs() {
  const [filters, setFilters] = useState<LogFilters>({});
  const [groups, setGroups] = useState<LogGroup[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await api.get(`/api/logs${buildQuery(filters)}`);
    if (res.ok && res.data) {
      const d = res.data as { groups: LogGroup[]; total_groups: number };
      setGroups(d.groups || []);
      setTotal(d.total_groups || 0);
    } else {
      setError(String(res.status));
    }
    setLoading(false);
  }, [filters]);

  useEffect(() => { void refresh(); }, [refresh]);

  const fetchGroup = useCallback(async (fp: string): Promise<LogOccurrence[]> => {
    const res = await api.get(`/api/logs/group/${encodeURIComponent(fp)}`);
    if (res.ok && res.data) return (res.data as { occurrences: LogOccurrence[] }).occurrences || [];
    return [];
  }, []);

  const markHandled = useCallback(async (fingerprints: string[]) => {
    await api.post('/api/logs/handle', { fingerprints });
    await refresh();
  }, [refresh]);

  const remove = useCallback(async (fingerprints: string[]): Promise<{ ok: boolean; status: number }> => {
    const res = await api.delete('/api/logs', { fingerprints });
    if (res.ok) await refresh();
    return { ok: res.ok, status: res.status };
  }, [refresh]);

  /** Télécharge les logs filtrés en fichier JSON (le « consigner »). */
  const exportLogs = useCallback(async () => {
    const res = await authFetch(`/api/logs/export${buildQuery(filters)}`);
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `precis-logs-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    URL.revokeObjectURL(url);
    document.body.removeChild(a);
  }, [filters]);

  return {
    filters, setFilters, groups, total, loading, error,
    refresh, fetchGroup, markHandled, remove, exportLogs,
  };
}
