/**
 * Journal des erreurs — vue d'administration (`/admin/logs`).
 *
 * Les erreurs (front, backend, API) arrivent regroupées par empreinte : une
 * ligne par défaut distinct, avec son nombre d'occurrences. On déplie pour voir
 * la pile et le contexte. Le cycle « consigner puis vider » se joue ici :
 * exporter (le fichier), marquer traité, puis seulement supprimer.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  RefreshCw, Download, CheckCircle2, Trash2, ChevronDown, ChevronRight,
} from 'lucide-react';

import { useErrorLogs, type LogOccurrence } from '../hooks/useErrorLogs';
import { showToast } from '../components/ui/Toast';
import AdminShell from '../components/admin/AdminShell';

const LEVEL_COLOR: Record<string, string> = {
  critical: '#b91c1c', error: '#dc2626', warning: '#d97706',
};
const SOURCE_LABEL: Record<string, string> = {
  frontend: 'front', backend: 'back', api: 'api',
};

function fmt(iso: string | null): string {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

export default function AdminLogsPage() {
  const { t } = useTranslation();
  const {
    filters, setFilters, groups, total, loading,
    refresh, fetchGroup, markHandled, remove, exportLogs,
  } = useErrorLogs();

  const [open, setOpen] = useState<string | null>(null);
  const [occ, setOcc] = useState<Record<string, LogOccurrence[]>>({});

  const toggle = async (fp: string) => {
    if (open === fp) { setOpen(null); return; }
    setOpen(fp);
    if (!occ[fp]) {
      const rows = await fetchGroup(fp);
      setOcc((o) => ({ ...o, [fp]: rows }));
    }
  };

  const onDelete = async (fp: string) => {
    const res = await remove([fp]);
    if (!res.ok && res.status === 409) {
      showToast('error', t('logs.delete_blocked_title', 'À traiter d’abord'),
        t('logs.delete_blocked', 'Exportez puis marquez « traité » avant de supprimer.'));
    } else if (res.ok) {
      showToast('success', t('logs.deleted', 'Supprimé'), '');
    }
  };

  const sel = (v: string) => (v === '' ? undefined : v);

  return (
    <AdminShell
      title={t('logs.title', 'Journal des erreurs')}
      count={t('logs.groups_count', '{{n}} type(s)', { n: total })}
      actions={
        <>
          <button onClick={() => void exportLogs()} className="tb-btn ghost"
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Download size={15} strokeWidth={2.2} /> {t('logs.export', 'Exporter')}
          </button>
          <button onClick={() => void refresh()} className="tb-btn ghost"
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <RefreshCw size={15} strokeWidth={2.2} /> {t('logs.refresh', 'Rafraîchir')}
          </button>
        </>
      }
    >
        {/* Filtres */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', flexWrap: 'wrap' }}>
          <select value={filters.source || ''} onChange={(e) => setFilters({ ...filters, source: sel(e.target.value) })} style={selectStyle}>
            <option value="">{t('logs.all_sources', 'Toutes sources')}</option>
            <option value="frontend">frontend</option>
            <option value="backend">backend</option>
            <option value="api">api</option>
          </select>
          <select value={filters.level || ''} onChange={(e) => setFilters({ ...filters, level: sel(e.target.value) })} style={selectStyle}>
            <option value="">{t('logs.all_levels', 'Tous niveaux')}</option>
            <option value="critical">critical</option>
            <option value="error">error</option>
            <option value="warning">warning</option>
          </select>
          <select value={filters.status || ''} onChange={(e) => setFilters({ ...filters, status: sel(e.target.value) })} style={selectStyle}>
            <option value="">{t('logs.all_status', 'Tous statuts')}</option>
            <option value="new">{t('logs.status_new', 'Nouveau')}</option>
            <option value="handled">{t('logs.status_handled', 'Traité')}</option>
          </select>
          <input
            value={filters.q || ''}
            onChange={(e) => setFilters({ ...filters, q: e.target.value || undefined })}
            placeholder={t('logs.search', 'Rechercher…')}
            style={{ ...selectStyle, flex: 1, minWidth: '160px' }}
          />
        </div>

        {/* Liste groupée */}
        {loading && <div style={{ color: 'var(--gray-500)', fontSize: '13px' }}>{t('logs.loading', 'Chargement…')}</div>}
        {!loading && groups.length === 0 && (
          <div style={{ padding: '48px', textAlign: 'center', color: 'var(--gray-500, #6b7280)', fontSize: '14px' }}>
            {t('logs.empty', 'Aucune erreur. Tout va bien.')}
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {groups.map((g) => (
            <div key={g.fingerprint} style={{
              background: '#fff', border: '1px solid var(--gray-200, #e5e7eb)',
              borderRadius: '10px', overflow: 'hidden',
            }}>
              {/* Ligne du groupe */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '12px 14px' }}>
                <button onClick={() => void toggle(g.fingerprint)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', display: 'flex', color: 'var(--gray-500)' }}>
                  {open === g.fingerprint ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                </button>
                <span style={{
                  fontSize: '10px', fontWeight: 700, letterSpacing: '0.03em',
                  color: '#fff', background: LEVEL_COLOR[g.level] || '#6b7280',
                  padding: '2px 7px', borderRadius: '999px', textTransform: 'uppercase',
                }}>{g.level}</span>
                <span style={{
                  fontSize: '11px', fontWeight: 600, color: 'var(--gray-600, #4b5563)',
                  background: 'var(--gray-100, #f3f4f6)', padding: '2px 7px', borderRadius: '6px',
                }}>{SOURCE_LABEL[g.source] || g.source}</span>
                <span style={{
                  fontSize: '13px', color: 'var(--navy, #0d1b3e)', flex: 1, minWidth: 0,
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  fontFamily: 'var(--font-mono, monospace)',
                }} title={g.message}>{g.message}</span>
                <span style={{
                  fontSize: '11px', fontWeight: 700, color: 'var(--navy)',
                  background: 'var(--blue-light, #eff6ff)', padding: '2px 8px', borderRadius: '999px',
                }}>×{g.count}</span>
                {g.status === 'handled' ? (
                  <span style={{ fontSize: '11px', color: '#16a34a', fontWeight: 600 }}>{t('logs.status_handled', 'Traité')}</span>
                ) : (
                  <span style={{ fontSize: '11px', color: '#d97706', fontWeight: 600 }}>{t('logs.status_new', 'Nouveau')}</span>
                )}
                <span style={{ fontSize: '11px', color: 'var(--gray-400, #9ca3af)', whiteSpace: 'nowrap' }}>{fmt(g.last_seen)}</span>
                {g.new_count > 0 && (
                  <button onClick={() => void markHandled([g.fingerprint])} title={t('logs.mark_handled', 'Marquer traité')}
                    className="tb-btn ghost" style={{ display: 'flex', padding: '5px' }}>
                    <CheckCircle2 size={15} strokeWidth={2.2} />
                  </button>
                )}
                <button onClick={() => void onDelete(g.fingerprint)} title={t('logs.delete', 'Supprimer')}
                  className="tb-btn ghost" style={{ display: 'flex', padding: '5px', color: '#dc2626' }}>
                  <Trash2 size={15} strokeWidth={2.2} />
                </button>
              </div>

              {/* Détail : occurrences */}
              {open === g.fingerprint && (
                <div style={{ borderTop: '1px solid var(--gray-100, #f3f4f6)', background: 'var(--gray-50, #f9fafb)', padding: '10px 14px' }}>
                  {(occ[g.fingerprint] || []).map((o) => (
                    <div key={o.id} style={{ padding: '8px 0', borderBottom: '1px solid var(--gray-100, #f3f4f6)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--gray-500)', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                        <span>{fmt(o.created_at)}</span>
                        {o.user_email && <span>👤 {o.user_email}</span>}
                        {o.context?.url ? <span>{String(o.context.url)}</span> : null}
                      </div>
                      {o.stack && (
                        <pre style={{
                          fontSize: '11px', color: 'var(--gray-700, #374151)', marginTop: '6px',
                          whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: '180px',
                          overflow: 'auto', fontFamily: 'var(--font-mono, monospace)',
                        }}>{o.stack}</pre>
                      )}
                      {o.context && Object.keys(o.context).length > 0 && (
                        <pre style={{ fontSize: '10.5px', color: 'var(--gray-500)', marginTop: '4px', whiteSpace: 'pre-wrap' }}>
                          {JSON.stringify(o.context, null, 2)}
                        </pre>
                      )}
                    </div>
                  ))}
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
