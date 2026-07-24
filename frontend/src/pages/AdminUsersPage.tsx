/**
 * Comptes utilisateurs — vue d'administration (`/admin/users`).
 *
 * Le seul geste ici : changer le plan d'un compte pour ouvrir Précis à un
 * testeur sans desserrer le forfait Gratuit. On ne crée ni ne supprime de
 * compte — c'est un outil de promotion, pas un gestionnaire complet.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { RefreshCw, Search } from 'lucide-react';

import { useAdminUsers, type AdminUser } from '../hooks/useAdminUsers';
import { useAuth } from '../contexts/AuthContext';
import { showToast } from '../components/ui/Toast';
import AdminShell from '../components/admin/AdminShell';

const PLAN_COLOR: Record<string, string> = {
  free: '#6b7280', starter: '#2563eb', pro: '#7c3aed',
  enterprise: '#0d9488', admin: '#b91c1c',
};

function fmt(iso: string | null): string {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString(); } catch { return iso; }
}

export default function AdminUsersPage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { q, setQ, users, plans, total, loading, refresh, changePlan } = useAdminUsers();
  const [busy, setBusy] = useState<string | null>(null);

  const onChange = async (u: AdminUser, plan: string) => {
    if (plan === u.plan) return;
    setBusy(u.id);
    const res = await changePlan(u.id, plan);
    setBusy(null);
    if (res.ok) {
      showToast('success', t('admin_users.changed', 'Plan modifié'), u.email);
    } else if (res.status === 400) {
      showToast('error', t('admin_users.change_refused_title', 'Changement refusé'),
        t('admin_users.change_refused', 'Un admin ne peut pas changer son propre plan.'));
    } else {
      showToast('error', t('admin_users.change_error', 'Échec'), String(res.status));
    }
  };

  return (
    <AdminShell
      title={t('admin_users.title', 'Comptes utilisateurs')}
      count={t('admin_users.count', '{{n}} compte(s)', { n: total })}
      actions={
        <button onClick={() => void refresh()} className="tb-btn ghost"
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <RefreshCw size={15} strokeWidth={2.2} /> {t('admin_users.refresh', 'Rafraîchir')}
        </button>
      }
    >
        {/* Recherche */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', alignItems: 'center' }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <Search size={15} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--gray-400)' }} />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={t('admin_users.search', 'Rechercher un e-mail ou un nom…')}
              style={{
                width: '100%', padding: '8px 10px 8px 32px', borderRadius: '8px',
                border: '1px solid var(--gray-200, #e5e7eb)', background: '#fff',
                color: 'var(--gray-700, #374151)', fontSize: '13px', fontFamily: 'inherit',
              }}
            />
          </div>
        </div>

        {loading && <div style={{ color: 'var(--gray-500)', fontSize: '13px' }}>{t('admin_users.loading', 'Chargement…')}</div>}
        {!loading && users.length === 0 && (
          <div style={{ padding: '48px', textAlign: 'center', color: 'var(--gray-500, #6b7280)', fontSize: '14px' }}>
            {t('admin_users.empty', 'Aucun compte.')}
          </div>
        )}

        {/* Table */}
        {users.length > 0 && (
          <div style={{ background: '#fff', border: '1px solid var(--gray-200, #e5e7eb)', borderRadius: '10px', overflow: 'hidden' }}>
            {users.map((u, i) => {
              const isSelf = user?.id === u.id;
              return (
                <div key={u.id} style={{
                  display: 'flex', alignItems: 'center', gap: '12px', padding: '12px 14px',
                  borderTop: i === 0 ? 'none' : '1px solid var(--gray-100, #f3f4f6)',
                }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--navy, #0d1b3e)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {u.email}{isSelf && <span style={{ marginLeft: '6px', fontSize: '11px', color: 'var(--gray-400)' }}>{t('admin_users.you', '(vous)')}</span>}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--gray-500)' }}>
                      {u.name || '—'} · {t('admin_users.since', 'inscrit le {{d}}', { d: fmt(u.created_at) })}
                      {!u.email_verified && <span style={{ marginLeft: '6px', color: '#d97706' }}>{t('admin_users.unverified', 'non vérifié')}</span>}
                    </div>
                  </div>
                  <span style={{
                    fontSize: '10px', fontWeight: 700, letterSpacing: '0.03em', color: '#fff',
                    background: PLAN_COLOR[u.plan] || '#6b7280', padding: '2px 8px',
                    borderRadius: '999px', textTransform: 'uppercase',
                  }}>{u.plan}</span>
                  <select
                    value={u.plan}
                    disabled={isSelf || busy === u.id}
                    onChange={(e) => void onChange(u, e.target.value)}
                    title={isSelf ? t('admin_users.cant_self', 'Vous ne pouvez pas changer votre propre plan') : ''}
                    style={{
                      padding: '6px 8px', borderRadius: '8px', border: '1px solid var(--gray-200, #e5e7eb)',
                      background: isSelf ? 'var(--gray-100)' : '#fff', color: 'var(--gray-700, #374151)',
                      fontSize: '12px', fontFamily: 'inherit', cursor: isSelf ? 'not-allowed' : 'pointer',
                    }}
                  >
                    {plans.map((p) => <option key={p} value={p}>{p}</option>)}
                  </select>
                </div>
              );
            })}
          </div>
        )}
    </AdminShell>
  );
}
