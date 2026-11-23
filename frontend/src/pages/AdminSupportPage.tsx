/**
 * Assistance — vue d'administration (`/admin/support`).
 *
 * Les demandes des utilisateurs arrivent ici : signalements de problème, aide
 * sur l'abonnement. On déplie pour lire le message, puis on traite (avec une
 * note interne) et on supprime — la suppression est refusée tant qu'un ticket
 * est encore ouvert.
 */
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { CheckCircle2, Trash2, ChevronDown, ChevronRight } from 'lucide-react';

import { useAdminSupport, type Ticket, type TicketFilters } from '../hooks/useAdminSupport';
import { useAdminUrlParams } from '../hooks/useAdminUrlParams';
import { showToast } from '../components/ui/Toast';
import AdminShell from '../components/admin/AdminShell';
import { UserLink } from '../components/admin/UserPanel';
import { AdminList, AdminToolbar, RefreshButton } from '../components/admin/AdminParts';

const CAT_COLOR: Record<string, string> = {
  problem: '#dc2626', subscription: '#2563eb', other: '#6b7280',
};

const URL_KEYS = ['q', 'category', 'status'] as const;

function fmt(iso: string | null): string {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

export default function AdminSupportPage() {
  const { t } = useTranslation();
  const { values, setValues, clear } = useAdminUrlParams(URL_KEYS);
  const filters = useMemo<TicketFilters>(() => ({
    q: values.q || undefined, category: values.category || undefined, status: values.status || undefined,
  }), [values]);
  const { tickets, total, openCount, loading, refresh, handle, remove } = useAdminSupport(filters);
  const [open, setOpen] = useState<string | null>(null);

  const catLabel = (c: string) =>
    t(`support.cat_${c}`, c === 'problem' ? 'Problème' : c === 'subscription' ? 'Abonnement' : 'Autre');

  const onHandle = async (ticket: Ticket) => {
    const note = window.prompt(t('support.note_prompt', 'Note interne (facultatif) — ce qui a été fait :')) ?? undefined;
    await handle([ticket.id], note);
    showToast('success', t('support.handled', 'Marqué traité'), ticket.subject);
  };

  const onDelete = async (ticket: Ticket) => {
    const res = await remove([ticket.id]);
    if (!res.ok && res.status === 409) {
      showToast('error', t('support.delete_blocked_title', 'À traiter d’abord'),
        t('support.delete_blocked', 'Marquez le ticket « traité » avant de le supprimer.'));
    } else if (res.ok) {
      showToast('success', t('support.deleted', 'Supprimé'), '');
    }
  };

  const hasFilters = Object.values(filters).some(Boolean);

  // Chiffres calculés sur la liste déjà chargée (aucun appel de plus).
  const stats = [
    { label: t('admin_support.stats.shown', 'Demandes affichées'), value: tickets.length },
    { label: t('admin_support.stats.open', 'Ouvertes'), value: tickets.filter((tk) => tk.status === 'open').length },
    { label: t('admin_support.stats.handled', 'Traitées'), value: tickets.filter((tk) => tk.status === 'handled').length },
  ];

  return (
    <AdminShell
      title={t('support.admin_title', 'Assistance')}
      count={t('support.count', '{{n}} ticket(s) · {{o}} ouvert(s)', { n: total, o: openCount })}
      stats={stats}
      actions={<RefreshButton onClick={() => void refresh()} disabled={loading} />}
    >
      <AdminToolbar
        search={filters.q || ''}
        onSearch={(v) => setValues({ q: v })}
        placeholder={t('support.search', 'Rechercher…')}
      >
        <select className="admin-select" value={filters.category || ''} onChange={(e) => setValues({ category: e.target.value })}>
          <option value="">{t('support.all_categories', 'Toutes catégories')}</option>
          <option value="problem">{catLabel('problem')}</option>
          <option value="subscription">{catLabel('subscription')}</option>
          <option value="other">{catLabel('other')}</option>
        </select>
        <select className="admin-select" value={filters.status || ''} onChange={(e) => setValues({ status: e.target.value })}>
          <option value="">{t('support.all_status', 'Tous statuts')}</option>
          <option value="open">{t('support.status_open', 'Ouvert')}</option>
          <option value="handled">{t('support.status_handled', 'Traité')}</option>
        </select>
      </AdminToolbar>

      <AdminList
        loading={loading}
        empty={tickets.length === 0}
        emptyText={t('support.empty', 'Aucune demande. Tout est calme.')}
        onClearFilters={hasFilters ? clear : undefined}
      >
        {tickets.map((tk) => {
          const isOpen = open === tk.id;
          return (
            <div key={tk.id} className="admin-item">
              <div className="admin-item__head">
                <button className="admin-row admin-row--button" aria-expanded={isOpen}
                  onClick={() => setOpen(isOpen ? null : tk.id)}>
                  {isOpen ? <ChevronDown size={16} className="admin-chevron" /> : <ChevronRight size={16} className="admin-chevron" />}
                  <div className="admin-row__main">
                    <div className="admin-row__title" title={tk.subject}>{tk.subject}</div>
                    <div className="admin-row__meta">
                      {tk.user_email ? `${tk.user_email} · ` : ''}{fmt(tk.created_at)}
                    </div>
                  </div>
                  <div className="admin-row__side">
                    <span className="admin-tag" style={{ background: CAT_COLOR[tk.category] || '#6b7280', color: '#fff' }}>{catLabel(tk.category)}</span>
                    {tk.status === 'handled' ? (
                      <span className="admin-tag" style={{ background: '#dcfce7', color: '#16a34a' }}>{t('support.status_handled', 'Traité')}</span>
                    ) : (
                      <span className="admin-tag" style={{ background: '#fef3c7', color: '#d97706' }}>{t('support.status_open', 'Ouvert')}</span>
                    )}
                  </div>
                </button>
                {tk.status === 'open' && (
                  <button onClick={() => void onHandle(tk)} title={t('support.mark_handled', 'Marquer traité')}
                    className="tb-btn ghost admin-icon-btn">
                    <CheckCircle2 size={15} strokeWidth={2.2} />
                  </button>
                )}
                <button onClick={() => void onDelete(tk)} title={t('support.delete', 'Supprimer')}
                  className="tb-btn ghost admin-icon-btn admin-icon-btn--danger">
                  <Trash2 size={15} strokeWidth={2.2} />
                </button>
              </div>

              {isOpen && (
                <div className="admin-detail">
                  <div className="admin-detail__meta">
                    {tk.user_email && <span>👤 <UserLink email={tk.user_email} /></span>}
                    {tk.context?.plan ? <span>{t('support.plan_label', 'forfait')} : {String(tk.context.plan)}</span> : null}
                    {tk.context?.url ? <span>{String(tk.context.url)}</span> : null}
                  </div>
                  {/* Document référencé automatiquement, s'il y en a un. */}
                  {tk.context?.document_name ? (
                    <div className="admin-detail__doc">
                      📄 {t('support.document_label', 'Document')} : <strong>{String(tk.context.document_name)}</strong>
                      {tk.context?.document_id ? <span className="admin-mono">· {String(tk.context.document_id)}</span> : null}
                    </div>
                  ) : null}
                  <p className="admin-detail__text">{tk.message}</p>
                  {tk.admin_note && (
                    <p className="admin-detail__note">
                      {t('support.note_label', 'Note interne')} : {tk.admin_note}
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </AdminList>
    </AdminShell>
  );
}
