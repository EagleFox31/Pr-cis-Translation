/**
 * Données de la console d'administration des comptes (`/admin/users`).
 *
 * Une seule action réelle : changer le plan d'un compte, pour promouvoir un
 * testeur sans toucher au forfait Gratuit. La liste est en lecture, filtrable
 * par e-mail ou nom.
 */
import { useCallback, useEffect, useState } from 'react';
import api from '../services/api';

export interface AdminUser {
  id: string;
  email: string;
  name: string | null;
  plan: string;
  priority: number;
  page_credits: number;
  storage_used: number;
  email_verified: boolean;
  created_at: string | null;
}

export function useAdminUsers() {
  const [q, setQ] = useState('');
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [plans, setPlans] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    const query = q ? `?q=${encodeURIComponent(q)}` : '';
    const res = await api.get(`/api/admin/users${query}`);
    if (res.ok && res.data) {
      const d = res.data as { users: AdminUser[]; total: number; assignable_plans: string[] };
      setUsers(d.users || []);
      setTotal(d.total || 0);
      setPlans(d.assignable_plans || []);
    } else {
      setError(String(res.status));
    }
    setLoading(false);
  }, [q]);

  useEffect(() => { void refresh(); }, [refresh]);

  /** Change le plan d'un compte. Renvoie l'issue pour que l'appelant affiche le
   *  bon message (400 = refus métier, ex. changer son propre plan). */
  const changePlan = useCallback(
    async (userId: string, plan: string): Promise<{ ok: boolean; status: number }> => {
      const res = await api.post(`/api/admin/users/${encodeURIComponent(userId)}/plan`, { plan });
      if (res.ok) await refresh();
      return { ok: res.ok, status: res.status };
    },
    [refresh],
  );

  return { q, setQ, users, plans, total, loading, error, refresh, changePlan };
}
