/**
 * Données de la vue d'administration de l'assistance (`/admin/support`).
 *
 * Liste filtrable des tickets, et les deux gestes du cycle « traiter puis
 * vider » : marquer traité (avec note interne), supprimer (refusé tant qu'un
 * ticket visé est encore ouvert).
 */
import { useCallback, useEffect, useState } from 'react';
import api from '../services/api';

export interface Ticket {
  id: string;
  category: string;
  subject: string;
  message: string;
  context: Record<string, unknown> | null;
  user_email: string | null;
  status: 'open' | 'handled';
  admin_note: string | null;
  handled_at: string | null;
  created_at: string | null;
}

export interface TicketFilters {
  category?: string;
  status?: string;
  q?: string;
}

function buildQuery(f: TicketFilters): string {
  const p = new URLSearchParams();
  if (f.category) p.set('category', f.category);
  if (f.status) p.set('status', f.status);
  if (f.q) p.set('q', f.q);
  const s = p.toString();
  return s ? `?${s}` : '';
}

export function useAdminSupport() {
  const [filters, setFilters] = useState<TicketFilters>({});
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [total, setTotal] = useState(0);
  const [openCount, setOpenCount] = useState(0);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    const res = await api.get(`/api/support${buildQuery(filters)}`);
    if (res.ok && res.data) {
      const d = res.data as { tickets: Ticket[]; total: number; open_count: number };
      setTickets(d.tickets || []);
      setTotal(d.total || 0);
      setOpenCount(d.open_count || 0);
    }
    setLoading(false);
  }, [filters]);

  useEffect(() => { void refresh(); }, [refresh]);

  const handle = useCallback(async (ids: string[], note?: string) => {
    await api.post('/api/support/handle', { ids, note: note || null });
    await refresh();
  }, [refresh]);

  const remove = useCallback(
    async (ids: string[]): Promise<{ ok: boolean; status: number }> => {
      const res = await api.delete('/api/support', { ids });
      if (res.ok) await refresh();
      return { ok: res.ok, status: res.status };
    },
    [refresh],
  );

  return { filters, setFilters, tickets, total, openCount, loading, refresh, handle, remove };
}
