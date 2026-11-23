/**
 * Briques du gabarit admin (docs/etude-interfaces-admin.md § 3) : chaque page
 * les remplit au lieu de redessiner sa barre, sa liste et son état vide.
 */
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { File as FileIcon, FileText, FileType2, Inbox, Presentation, RefreshCw, Search, Sheet } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

// Mêmes icônes que la bibliothèque (DocumentCard), couleur du logiciel d'origine.
const EXT_ICONS: Record<string, LucideIcon> = { pdf: FileType2, docx: FileText, pptx: Presentation, xlsx: Sheet, txt: FileText };

/** Icône du type de fichier, d'après une extension (`pdf`) ou un nom (`cv.pdf`). */
export function FileTypeIcon({ name, size = 16 }: { name: string; size?: number }) {
  const ext = name.split('.').pop()?.toLowerCase() ?? '';
  const Icon = EXT_ICONS[ext] ?? FileIcon;
  return <Icon size={size} strokeWidth={2} aria-hidden className={`admin-doc-icon admin-doc-icon--${ext}`} />;
}

export interface AdminStat { label: string; value: ReactNode }

export function AdminStats({ items }: { items: AdminStat[] }) {
  return (
    <div className="admin-stats">
      {items.map((s) => <div key={s.label} className="admin-stat"><strong>{s.value}</strong><span>{s.label}</span></div>)}
    </div>
  );
}

/** Le bouton d'actualisation, identique sur toutes les pages. */
export function RefreshButton({ onClick, disabled }: { onClick: () => void; disabled?: boolean }) {
  const { t } = useTranslation();
  return (
    <button className="tb-btn ghost admin-btn" onClick={onClick} disabled={disabled}>
      <RefreshCw size={15} strokeWidth={2.2} /> {t('admin.refresh', 'Actualiser')}
    </button>
  );
}

/** Recherche (extensible) suivie des filtres passés en enfants. */
export function AdminToolbar({ search, onSearch, placeholder, children }: {
  search?: string; onSearch?: (v: string) => void; placeholder?: string; children?: ReactNode;
}) {
  return (
    <div className="admin-toolbar">
      {onSearch && (
        <div className="admin-search">
          <Search size={15} />
          <input className="admin-input" type="search" value={search ?? ''} placeholder={placeholder}
            aria-label={placeholder} onChange={(e) => onSearch(e.target.value)} />
        </div>
      )}
      {children}
    </div>
  );
}

/** La carte de liste : chargement, état vide ou contenu, toujours au même endroit. */
export function AdminList({ loading, empty, emptyText, onClearFilters, children }: {
  loading?: boolean; empty: boolean; emptyText: string; onClearFilters?: () => void; children?: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <div className="admin-list">
      {loading && empty ? (
        <div className="admin-loading" role="status">{t('admin.loading', 'Chargement…')}</div>
      ) : empty ? (
        <div className="admin-empty">
          <Inbox size={32} strokeWidth={1.6} />
          <span>{emptyText}</span>
          {onClearFilters && <button onClick={onClearFilters}>{t('admin.clear_filters', 'Effacer les filtres')}</button>}
        </div>
      ) : children}
    </div>
  );
}
