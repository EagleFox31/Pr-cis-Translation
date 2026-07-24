/**
 * Assistance — vue d'administration (`/admin/support`).
 *
 * Les demandes des utilisateurs arrivent ici : signalements de problème, aide
 * sur l'abonnement. On déplie pour lire le message, puis on traite (avec une
 * note interne) et on supprime — la suppression est refusée tant qu'un ticket
 * est encore ouvert.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { RefreshCw, CheckCircle2, Trash2, ChevronDown, ChevronRight } from 'lucide-react';

import { useAdminSupport, type Ticket } from '../hooks/useAdminSupport';
import { showToast } from '../components/ui/Toast';
import AdminShell from '../components/admin/AdminShell';

const CAT_COLOR: Record<string, string> = {
  problem: '#dc2626', subscription: '#2563eb', other: '#6b7280',
};

function fmt(iso: string | null): string {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

export default function AdminSupportPage() {
  const { t } = useTranslation();
  const { filters, setFilters, tickets, total, openCount, loading, refresh, handle, remove } = useAdminSupport();
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

  const sel = (v: string) => (v === '' ? undefined : v);

  return (
    <AdminShell
      title={t('support.admin_title', 'Assistance')}
      count={t('support.count', '{{n}} ticket(s) · {{o}} ouvert(s)', { n: total, o: openCount })}
      actions={
        <button onClick={() => void refresh()} className="tb-btn ghost"
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <RefreshCw size={15} strokeWidth={2.2} /> {t('support.refresh', 'Rafraîchir')}
        </button>
      }
    >
      {/* Filtres */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', flexWrap: 'wrap' }}>
        <select value={filters.category || ''} onChange={(e) => setFilters({ ...filters, category: sel(e.target.value) })} style={selectStyle}>
          <option value="">{t('support.all_categories', 'Toutes catégories')}</option>
          <option value="problem">{catLabel('problem')}</option>
          <option value="subscription">{catLabel('subscription')}</option>
          <option value="other">{catLabel('other')}</option>
        </select>
        <select value={filters.status || ''} onChange={(e) => setFilters({ ...filters, status: sel(e.target.value) })} style={selectStyle}>
          <option value="">{t('support.all_status', 'Tous statuts')}</option>
          <option value="open">{t('support.status_open', 'Ouvert')}</option>
          <option value="handled">{t('support.status_handled', 'Traité')}</option>
        </select>
        <input
          value={filters.q || ''}
          onChange={(e) => setFilters({ ...filters, q: e.target.value || undefined })}
          placeholder={t('support.search', 'Rechercher…')}
          style={{ ...selectStyle, flex: 1, minWidth: '160px' }}
        />
      </div>

      {loading && <div style={{ color: 'var(--gray-500)', fontSize: '13px' }}>{t('support.loading', 'Chargement…')}</div>}
      {!loading && tickets.length === 0 && (
        <div style={{ padding: '48px', textAlign: 'center', color: 'var(--gray-500, #6b7280)', fontSize: '14px' }}>
          {t('support.empty', 'Aucune demande. Tout est calme.')}
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {tickets.map((tk) => (
          <div key={tk.id} style={{
            background: '#fff', border: '1px solid var(--gray-200, #e5e7eb)',
            borderRadius: '10px', overflow: 'hidden',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '12px 14px' }}>
              <button onClick={() => setOpen(open === tk.id ? null : tk.id)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', display: 'flex', color: 'var(--gray-500)' }}>
                {open === tk.id ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
              </button>
              <span style={{
                fontSize: '10px', fontWeight: 700, letterSpacing: '0.03em', color: '#fff',
                background: CAT_COLOR[tk.category] || '#6b7280', padding: '2px 8px',
                borderRadius: '999px', textTransform: 'uppercase',
              }}>{catLabel(tk.category)}</span>
              <span style={{
                fontSize: '13px', color: 'var(--navy, #0d1b3e)', flex: 1, minWidth: 0,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: 600,
              }} title={tk.subject}>{tk.subject}</span>
              {tk.status === 'handled' ? (
                <span style={{ fontSize: '11px', color: '#16a34a', fontWeight: 600 }}>{t('support.status_handled', 'Traité')}</span>
              ) : (
                <span style={{ fontSize: '11px', color: '#d97706', fontWeight: 600 }}>{t('support.status_open', 'Ouvert')}</span>
              )}
              <span style={{ fontSize: '11px', color: 'var(--gray-400, #9ca3af)', whiteSpace: 'nowrap' }}>{fmt(tk.created_at)}</span>
              {tk.status === 'open' && (
                <button onClick={() => void onHandle(tk)} title={t('support.mark_handled', 'Marquer traité')}
                  className="tb-btn ghost" style={{ display: 'flex', padding: '5px' }}>
                  <CheckCircle2 size={15} strokeWidth={2.2} />
                </button>
              )}
              <button onClick={() => void onDelete(tk)} title={t('support.delete', 'Supprimer')}
                className="tb-btn ghost" style={{ display: 'flex', padding: '5px', color: '#dc2626' }}>
                <Trash2 size={15} strokeWidth={2.2} />
              </button>
            </div>

            {open === tk.id && (
              <div style={{ borderTop: '1px solid var(--gray-100, #f3f4f6)', background: 'var(--gray-50, #f9fafb)', padding: '12px 16px' }}>
                <div style={{ fontSize: '12px', color: 'var(--gray-500)', marginBottom: 8, display: 'flex', gap: 14, flexWrap: 'wrap' }}>
                  {tk.user_email && <span>👤 {tk.user_email}</span>}
                  {tk.context?.plan ? <span>{t('support.plan_label', 'forfait')} : {String(tk.context.plan)}</span> : null}
                  {tk.context?.url ? <span>{String(tk.context.url)}</span> : null}
                </div>
                {/* Document référencé automatiquement, s'il y en a un. */}
                {tk.context?.document_name ? (
                  <div style={{
                    fontSize: '12.5px', marginBottom: 10, padding: '7px 10px', borderRadius: '8px',
                    background: 'var(--blue-light, #eff6ff)', border: '1px solid #bfdbfe',
                    color: '#1e40af', display: 'inline-flex', alignItems: 'center', gap: 6,
                  }}>
                    📄 {t('support.document_label', 'Document')} : <strong>{String(tk.context.document_name)}</strong>
                    {tk.context?.document_id ? <span style={{ color: 'var(--gray-400)' }}>· {String(tk.context.document_id)}</span> : null}
                  </div>
                ) : null}
                <p style={{ fontSize: '13.5px', color: 'var(--gray-800, #1f2937)', whiteSpace: 'pre-wrap', margin: 0, lineHeight: 1.55 }}>
                  {tk.message}
                </p>
                {tk.admin_note && (
                  <p style={{ marginTop: 10, fontSize: '12.5px', color: 'var(--gray-600)', fontStyle: 'italic' }}>
                    {t('support.note_label', 'Note interne')} : {tk.admin_note}
                  </p>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </AdminShell>
  );
}

const selectStyle: React.CSSProperties = {
  padding: '7px 10px', borderRadius: '8px', border: '1px solid var(--gray-200, #e5e7eb)',
  background: '#fff', color: 'var(--gray-700, #374151)', fontSize: '13px',
  fontFamily: 'inherit', cursor: 'pointer',
};
