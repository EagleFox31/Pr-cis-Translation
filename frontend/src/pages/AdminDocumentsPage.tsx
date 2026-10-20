/**
 * Documents de tous les comptes — vue d'administration (`/admin/documents`).
 *
 * Sert à diagnostiquer un rendu cassé : on retrouve le document d'un
 * utilisateur (par e-mail ou nom de fichier) et on télécharge son original et
 * sa traduction. Lecture seule, chaque téléchargement est journalisé côté
 * serveur.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Download, RefreshCw, Search } from 'lucide-react';

import { useAdminDocuments, type AdminDocKind, type AdminDocument } from '../hooks/useAdminDocuments';
import { showToast } from '../components/ui/Toast';
import AdminShell from '../components/admin/AdminShell';

function fmt(iso: string | null): string {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString(); } catch { return iso; }
}

const cell: React.CSSProperties = { padding: '10px 12px', fontSize: '13px', color: 'var(--gray-700, #374151)' };
const head: React.CSSProperties = {
  ...cell, fontSize: '11px', fontWeight: 700, textTransform: 'uppercase',
  letterSpacing: '0.03em', color: 'var(--gray-500, #6b7280)', textAlign: 'left',
};
const ellipsis: React.CSSProperties = { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' };

export default function AdminDocumentsPage() {
  const { t } = useTranslation();
  const { q, setQ, items, total, loading, refresh, download } = useAdminDocuments();
  const [busy, setBusy] = useState<string | null>(null);

  const onDownload = async (doc: AdminDocument, kind: AdminDocKind) => {
    const key = `${doc.id}:${kind}`;
    setBusy(key);
    let status = 0;
    let ok = false;
    try {
      ({ ok, status } = await download(doc, kind));
    } catch {
      ok = false;
    }
    setBusy(null);
    if (!ok) {
      showToast('error', t('admin_docs.download_error', 'Téléchargement impossible'),
        status === 404
          ? t('admin_docs.file_missing', 'Le fichier n’est plus disponible.')
          : String(status || ''));
    }
  };

  const dlButton = (doc: AdminDocument, kind: AdminDocKind, available: boolean, label: string) => {
    const disabled = !available || busy === `${doc.id}:${kind}`;
    return (
      <button
        onClick={() => void onDownload(doc, kind)}
        disabled={disabled}
        title={available ? '' : t('admin_docs.absent', 'Fichier absent')}
        className="tb-btn ghost"
        style={{
          display: 'inline-flex', alignItems: 'center', gap: '5px', fontSize: '12px',
          opacity: disabled ? 0.45 : 1, cursor: disabled ? 'not-allowed' : 'pointer',
        }}
      >
        <Download size={13} strokeWidth={2.2} /> {label}
      </button>
    );
  };

  return (
    <AdminShell
      title={t('admin_docs.title', 'Documents des utilisateurs')}
      count={t('admin_docs.count', '{{n}} document(s)', { n: total })}
      actions={
        <button onClick={() => void refresh()} className="tb-btn ghost"
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <RefreshCw size={15} strokeWidth={2.2} /> {t('admin_docs.refresh', 'Rafraîchir')}
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
            placeholder={t('admin_docs.search', 'Rechercher un e-mail ou un nom de fichier…')}
            style={{
              width: '100%', padding: '8px 10px 8px 32px', borderRadius: '8px',
              border: '1px solid var(--gray-200, #e5e7eb)', background: '#fff',
              color: 'var(--gray-700, #374151)', fontSize: '13px', fontFamily: 'inherit',
            }}
          />
        </div>
      </div>

      {loading && <div style={{ color: 'var(--gray-500)', fontSize: '13px' }}>{t('admin_docs.loading', 'Chargement…')}</div>}
      {!loading && items.length === 0 && (
        <div style={{ padding: '48px', textAlign: 'center', color: 'var(--gray-500, #6b7280)', fontSize: '14px' }}>
          {t('admin_docs.empty', 'Aucun document.')}
        </div>
      )}

      {items.length > 0 && (
        <div style={{ background: '#fff', border: '1px solid var(--gray-200, #e5e7eb)', borderRadius: '10px', overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed', minWidth: '860px' }}>
            <thead>
              <tr style={{ background: 'var(--gray-50, #f9fafb)' }}>
                <th style={{ ...head, width: '24%' }}>{t('admin_docs.col_name', 'Nom')}</th>
                <th style={{ ...head, width: '22%' }}>{t('admin_docs.col_owner', 'Propriétaire')}</th>
                <th style={{ ...head, width: '9%' }}>{t('admin_docs.col_langs', 'Langues')}</th>
                <th style={{ ...head, width: '10%' }}>{t('admin_docs.col_status', 'Statut')}</th>
                <th style={{ ...head, width: '6%' }}>{t('admin_docs.col_pages', 'Pages')}</th>
                <th style={{ ...head, width: '10%' }}>{t('admin_docs.col_date', 'Date')}</th>
                <th style={{ ...head, width: '19%' }}>{t('admin_docs.col_files', 'Fichiers')}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((d) => (
                <tr key={d.id} style={{ borderTop: '1px solid var(--gray-100, #f3f4f6)' }}>
                  <td style={{ ...cell, ...ellipsis, fontWeight: 600, color: 'var(--navy, #0d1b3e)' }} title={d.original_name}>{d.original_name}</td>
                  <td style={{ ...cell, ...ellipsis }} title={d.user_email || ''}>{d.user_email || '—'}</td>
                  <td style={cell}>{d.source_lang} → {d.target_lang}</td>
                  <td style={cell}>{d.status}</td>
                  <td style={cell}>{d.page_count ?? '—'}</td>
                  <td style={cell}>{fmt(d.created_at)}</td>
                  <td style={{ ...cell, display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    {dlButton(d, 'original', d.has_original, t('admin_docs.original', 'Original'))}
                    {dlButton(d, 'translated', d.has_translation, t('admin_docs.translation', 'Traduction'))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </AdminShell>
  );
}
