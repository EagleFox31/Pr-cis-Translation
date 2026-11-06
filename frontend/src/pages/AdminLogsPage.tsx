/**
 * Journal des erreurs — vue d'administration (`/admin/logs`).
 *
 * Les erreurs (front, backend, API) arrivent regroupées par empreinte : une
 * ligne par défaut distinct, avec son nombre d'occurrences. On déplie pour voir
 * la pile et le contexte. Le cycle « consigner puis vider » se joue ici :
 * exporter (le fichier), marquer traité, puis seulement supprimer.
 */
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Download, CheckCircle2, Trash2, ChevronDown, ChevronRight,
} from 'lucide-react';

import { useErrorLogs, type LogFilters, type LogOccurrence } from '../hooks/useErrorLogs';
import { useAdminUrlParams } from '../hooks/useAdminUrlParams';
import { showToast } from '../components/ui/Toast';
import AdminShell from '../components/admin/AdminShell';
import { UserLink } from '../components/admin/UserPanel';
import { AdminList, AdminToolbar, RefreshButton } from '../components/admin/AdminParts';

const LEVEL_COLOR: Record<string, string> = {
  critical: '#b91c1c', error: '#dc2626', warning: '#d97706',
};
const SOURCE_LABEL: Record<string, string> = {
  frontend: 'front', backend: 'back', api: 'api',
};

const URL_KEYS = ['q', 'source', 'level', 'status'] as const;

function fmt(iso: string | null): string {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

export default function AdminLogsPage() {
  const { t } = useTranslation();
  const { values, setValues, clear } = useAdminUrlParams(URL_KEYS);
  const filters = useMemo<LogFilters>(() => ({
    q: values.q || undefined, source: values.source || undefined,
    level: values.level || undefined, status: values.status || undefined,
  }), [values]);
  const {
    groups, total, loading,
    refresh, fetchGroup, markHandled, remove, exportLogs,
  } = useErrorLogs(filters);

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

  const hasFilters = Object.values(filters).some(Boolean);

  // Chiffres calculés sur la liste déjà chargée (aucun appel de plus).
  const stats = [
    { label: t('admin_logs.stats.shown', 'Types affichés'), value: groups.length },
    { label: t('admin_logs.stats.unhandled', 'Non traités'), value: groups.filter((g) => g.status !== 'handled').length },
    { label: t('admin_logs.stats.errors', 'Erreurs'), value: groups.filter((g) => g.level === 'critical' || g.level === 'error').length },
    { label: t('admin_logs.stats.warnings', 'Avertissements'), value: groups.filter((g) => g.level === 'warning').length },
  ];

  return (
    <AdminShell
      title={t('logs.title', 'Journal des erreurs')}
      count={t('logs.groups_count', '{{n}} type(s)', { n: total })}
      stats={stats}
      actions={
        <>
          <button onClick={() => void exportLogs()} className="tb-btn ghost admin-btn">
            <Download size={15} strokeWidth={2.2} /> {t('logs.export', 'Exporter')}
          </button>
          <RefreshButton onClick={() => void refresh()} disabled={loading} />
        </>
      }
    >
      <AdminToolbar
        search={filters.q || ''}
        onSearch={(v) => setValues({ q: v })}
        placeholder={t('logs.search', 'Rechercher…')}
      >
        <select className="admin-select" value={filters.source || ''} onChange={(e) => setValues({ source: e.target.value })}>
          <option value="">{t('logs.all_sources', 'Toutes sources')}</option>
          <option value="frontend">frontend</option>
          <option value="backend">backend</option>
          <option value="api">api</option>
        </select>
        <select className="admin-select" value={filters.level || ''} onChange={(e) => setValues({ level: e.target.value })}>
          <option value="">{t('logs.all_levels', 'Tous niveaux')}</option>
          <option value="critical">critical</option>
          <option value="error">error</option>
          <option value="warning">warning</option>
        </select>
        <select className="admin-select" value={filters.status || ''} onChange={(e) => setValues({ status: e.target.value })}>
          <option value="">{t('logs.all_status', 'Tous statuts')}</option>
          <option value="new">{t('logs.status_new', 'Nouveau')}</option>
          <option value="handled">{t('logs.status_handled', 'Traité')}</option>
        </select>
      </AdminToolbar>

      {/* Liste groupée */}
      <AdminList
        loading={loading}
        empty={groups.length === 0}
        emptyText={t('logs.empty', 'Aucune erreur. Tout va bien.')}
        onClearFilters={hasFilters ? clear : undefined}
      >
        {groups.map((g) => {
          const isOpen = open === g.fingerprint;
          return (
            <div key={g.fingerprint} className="admin-item">
              {/* Ligne du groupe : la partie cliquable déplie, les actions restent à côté */}
              <div className="admin-item__head">
                <button className="admin-row admin-row--button" aria-expanded={isOpen}
                  onClick={() => void toggle(g.fingerprint)}>
                  {isOpen ? <ChevronDown size={16} className="admin-chevron" /> : <ChevronRight size={16} className="admin-chevron" />}
                  <div className="admin-row__main">
                    <div className="admin-row__title admin-row__title--log" title={g.message}>{g.message}</div>
                    <div className="admin-row__meta">
                      {SOURCE_LABEL[g.source] || g.source} · {fmt(g.last_seen)}
                    </div>
                  </div>
                  <div className="admin-row__side admin-row__side--log">
                    <span className="admin-tag" style={{ background: LEVEL_COLOR[g.level] || '#6b7280', color: '#fff' }}>{g.level}</span>
                    <span className="admin-tag">×{g.count}</span>
                    {g.status === 'handled' ? (
                      <span className="admin-tag" style={{ background: '#dcfce7', color: '#16a34a' }}>{t('logs.status_handled', 'Traité')}</span>
                    ) : (
                      <span className="admin-tag" style={{ background: '#fef3c7', color: '#d97706' }}>{t('logs.status_new', 'Nouveau')}</span>
                    )}
                  </div>
                </button>
                {g.new_count > 0 && (
                  <button onClick={() => void markHandled([g.fingerprint])} title={t('logs.mark_handled', 'Marquer traité')}
                    className="tb-btn ghost admin-icon-btn">
                    <CheckCircle2 size={15} strokeWidth={2.2} />
                  </button>
                )}
                <button onClick={() => void onDelete(g.fingerprint)} title={t('logs.delete', 'Supprimer')}
                  className="tb-btn ghost admin-icon-btn admin-icon-btn--danger">
                  <Trash2 size={15} strokeWidth={2.2} />
                </button>
              </div>

              {/* Détail : occurrences */}
              {isOpen && (
                <div className="admin-detail">
                  {(occ[g.fingerprint] || []).map((o) => (
                    <div key={o.id}>
                      <div className="admin-detail__meta">
                        <span>{fmt(o.created_at)}</span>
                        {o.user_email && <span>👤 <UserLink email={o.user_email} /></span>}
                        {o.context?.url ? <span>{String(o.context.url)}</span> : null}
                      </div>
                      {o.stack && <pre className="admin-pre admin-mono">{o.stack}</pre>}
                      {o.context && Object.keys(o.context).length > 0 && (
                        <pre className="admin-pre admin-mono">{JSON.stringify(o.context, null, 2)}</pre>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </AdminList>
    </AdminShell>
  );
}
