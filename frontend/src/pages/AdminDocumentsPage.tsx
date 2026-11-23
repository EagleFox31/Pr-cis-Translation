/**
 * Documents de tous les comptes — vue d'administration (`/admin/documents`).
 *
 * Sert à diagnostiquer un rendu cassé : on retrouve le document d'un
 * utilisateur (par e-mail ou nom de fichier) et on télécharge son original et
 * sa traduction, ou on les ouvre dans l'aperçu de l'accueil (« Aperçu »), d'où
 * l'on peut en garder une copie dans sa propre bibliothèque. Le document du
 * client n'est jamais modifié ; chaque lecture est journalisée côté serveur.
 */
import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Download, Eye } from 'lucide-react';

import { useAdminUrlParams } from '../hooks/useAdminUrlParams';
import { useAdminDocuments, type AdminDocKind, type AdminDocument } from '../hooks/useAdminDocuments';
import { showToast } from '../components/ui/Toast';
import AdminShell from '../components/admin/AdminShell';
import { UserLink } from '../components/admin/UserPanel';
import { useAuth } from '../contexts/AuthContext';
import type { DemandeApercuAdmin } from '../components/library/BibliothequeHote';
import { AdminList, AdminToolbar, FileTypeIcon, RefreshButton } from '../components/admin/AdminParts';

const URL_KEYS = ['q'] as const;

function fmt(iso: string | null): string {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString(); } catch { return iso; }
}

export default function AdminDocumentsPage() {
  const { t } = useTranslation();
  const { values, setValues } = useAdminUrlParams(URL_KEYS);
  const q = values.q;
  const setQ = (v: string) => setValues({ q: v });
  const { items, total, loading, refresh, download } = useAdminDocuments(q);
  const [busy, setBusy] = useState<string | null>(null);
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // L'aperçu est celui de l'accueil : on y part avec la demande, et son bouton
  // Retour ramène ici, recherche comprise. La copie n'est proposée que pour le
  // document d'un autre compte (le serveur refuse de copier le sien).
  const ouvrirApercu = (d: AdminDocument) => {
    const state: DemandeApercuAdmin = {
      apercuAdmin: {
        docId: d.id,
        nom: d.original_name,
        copiable: !d.copie_de && !!d.user_email && d.user_email !== user?.email,
        retour: location.pathname + location.search,
      },
    };
    navigate('/home', { state });
  };

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
        className="tb-btn ghost admin-btn"
      >
        <Download size={13} strokeWidth={2.2} /> {label}
      </button>
    );
  };

  return (
    <AdminShell
      title={t('admin_docs.title', 'Documents des utilisateurs')}
      count={t('admin_docs.count', '{{n}} document(s)', { n: total })}
      actions={<RefreshButton onClick={() => void refresh()} disabled={loading} />}
    >
      <AdminToolbar
        search={q}
        onSearch={setQ}
        placeholder={t('admin_docs.search', 'Rechercher un e-mail ou un nom de fichier…')}
      />

      <AdminList
        loading={loading}
        empty={items.length === 0}
        emptyText={t('admin_docs.empty', 'Aucun document.')}
        onClearFilters={q ? () => setQ('') : undefined}
      >
        <table className="admin-table admin-table--docs">
          <thead>
            <tr>
              <th>{t('admin_docs.col_name', 'Nom')}</th>
              <th>{t('admin_docs.col_owner', 'Propriétaire')}</th>
              <th>{t('admin_docs.col_langs', 'Langues')}</th>
              <th>{t('admin_docs.col_status', 'Statut')}</th>
              <th>{t('admin_docs.col_pages', 'Pages')}</th>
              <th>{t('admin_docs.col_date', 'Date')}</th>
              <th>{t('admin_docs.col_files', 'Fichiers')}</th>
            </tr>
          </thead>
          <tbody>
            {items.map((d) => (
              <tr key={d.id}>
                <td className="admin-cell-clip" title={d.original_name}><FileTypeIcon name={d.original_name} />{d.copie_de && <><span className="admin-tag">{t('admin_docs.copy_tag', 'Copie')}</span> </>}{d.original_name}</td>
                <td className="admin-cell-clip" title={d.user_email || ''}>{d.user_email ? <UserLink email={d.user_email} /> : '—'}</td>
                <td className="admin-cell-meta">{d.source_lang} → {d.target_lang}</td>
                <td className="admin-cell-meta"><span className={`admin-tag admin-tag--${d.status}`}>{t(`admin_docs.status_${d.status}`, d.status)}</span></td>
                <td className="admin-cell-meta">{d.page_count ?? '—'} <span className="admin-cell-unit">{t('admin_docs.pages_unit', 'p.')}</span></td>
                <td className="admin-cell-meta">{fmt(d.created_at)}</td>
                <td>
                  <div className="admin-cell-actions">
                    <button
                      onClick={() => ouvrirApercu(d)}
                      disabled={!d.has_translation}
                      title={d.has_translation ? '' : t('admin_docs.absent', 'Fichier absent')}
                      className="tb-btn ghost admin-btn"
                    >
                      <Eye size={13} strokeWidth={2.2} /> {t('admin_docs.preview', 'Aperçu')}
                    </button>
                    {dlButton(d, 'original', d.has_original, t('admin_docs.original', 'Original'))}
                    {dlButton(d, 'translated', d.has_translation, t('admin_docs.translation', 'Traduction'))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </AdminList>
    </AdminShell>
  );
}
