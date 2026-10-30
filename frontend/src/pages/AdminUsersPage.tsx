/**
 * Comptes utilisateurs — vue d'administration (`/admin/users`).
 *
 * Liste des comptes à gauche, fiche du compte choisi à droite
 * (docs/etude-fiche-utilisateur-integree.md). Le seul geste : changer le plan
 * d'un compte depuis sa fiche, pour ouvrir Précis à un testeur sans desserrer
 * le forfait Gratuit. On ne crée ni ne supprime de compte.
 */
import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
import { MousePointerClick } from 'lucide-react';

import { useAdminUsers } from '../hooks/useAdminUsers';
import { useAdminUrlParams } from '../hooks/useAdminUrlParams';
import { useAuth } from '../contexts/AuthContext';
import AdminShell from '../components/admin/AdminShell';
import { USER_PARAM, UserCard } from '../components/admin/UserPanel';
import { USERS_CHANGED_EVENT } from '../components/admin/planChange';
import { AdminList, AdminToolbar, RefreshButton } from '../components/admin/AdminParts';

const URL_KEYS = ['q'] as const;

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
  const { values, setValues } = useAdminUrlParams(URL_KEYS);
  const q = values.q;
  const setQ = (v: string) => setValues({ q: v });
  const { users, total, loading, refresh } = useAdminUsers(q);
  const [params, setParams] = useSearchParams();
  const selected = params.get(USER_PARAM);
  const cardRef = useRef<HTMLDivElement>(null);

  const select = (email: string | null) => setParams((prev) => {
    const next = new URLSearchParams(prev);
    if (email) next.set(USER_PARAM, email); else next.delete(USER_PARAM);
    return next;
  }, { replace: !email });

  // Une colonne (mobile) : la fiche passe au-dessus de la liste, on la montre.
  useEffect(() => {
    if (selected && window.matchMedia('(max-width: 899px)').matches) {
      cardRef.current?.scrollIntoView({ block: 'start' });
    }
  }, [selected]);

  // La fiche peut changer un plan : la liste se remet à jour.
  useEffect(() => {
    const onChanged = () => { void refresh(); };
    window.addEventListener(USERS_CHANGED_EVENT, onChanged);
    return () => window.removeEventListener(USERS_CHANGED_EVENT, onChanged);
  }, [refresh]);

  const isSelected = (email: string) => !!selected && email.toLowerCase() === selected.toLowerCase();

  return (
    <AdminShell
      title={t('admin_users.title', 'Comptes utilisateurs')}
      count={t('admin_users.count', '{{n}} compte(s)', { n: total })}
      actions={<RefreshButton onClick={() => void refresh()} disabled={loading} />}
    >
      <AdminToolbar
        search={q}
        onSearch={setQ}
        placeholder={t('admin_users.search', 'Rechercher un e-mail ou un nom…')}
      />

      <div className={`admin-duo${selected ? ' admin-duo--open' : ''}`}>
        <AdminList
          loading={loading}
          empty={users.length === 0}
          emptyText={t('admin_users.empty', 'Aucun compte.')}
          onClearFilters={q ? () => setQ('') : undefined}
        >
          {users.map((u) => {
            const isSelf = user?.id === u.id;
            const color = PLAN_COLOR[u.plan] || '#6b7280';
            return (
              <button
                key={u.id}
                type="button"
                className="admin-row admin-row--button admin-duo__row"
                aria-current={isSelected(u.email) ? 'true' : undefined}
                onClick={() => select(u.email)}
              >
                <div className="admin-row__main">
                  <div className="admin-row__title" title={u.email}>
                    {u.email}{isSelf && <> {t('admin_users.you', '(vous)')}</>}
                  </div>
                  <div className="admin-row__meta">
                    {u.name && <>{u.name} · </>}{t('admin_users.since', 'inscrit le {{d}}', { d: fmt(u.created_at) })}
                    {!u.email_verified && <> · {t('admin_users.unverified', 'non vérifié')}</>}
                  </div>
                </div>
                <span className="admin-tag" style={{ color, background: `${color}14`, border: `1px solid ${color}55` }}>{u.plan}</span>
              </button>
            );
          })}
        </AdminList>

        <div ref={cardRef} className="admin-duo__card">
          {selected ? (
            <UserCard key={selected} email={selected} onClose={() => select(null)} />
          ) : (
            <p className="admin-duo__invite">
              <MousePointerClick size={18} strokeWidth={2} aria-hidden="true" />
              {t('admin_users.pick', 'Choisissez un compte dans la liste pour voir sa fiche.')}
            </p>
          )}
        </div>
      </div>
    </AdminShell>
  );
}
