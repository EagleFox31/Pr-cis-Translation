import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { useTranslation } from 'react-i18next';
import type { DocMeta } from '../../hooks/useDocumentLibrary';

const EXT_ICONS: Record<string, string> = {
  pdf: '📄',
  docx: '📝',
  pptx: '📊',
  txt: '📃',
};

const LANG_LABELS: Record<string, string> = {
  'fr-FR': 'FR', 'fr': 'FR',
  'en-US': 'EN', 'en': 'EN',
  'es': 'ES', 'de': 'DE', 'it': 'IT',
  'pt-BR': 'PT', 'pt': 'PT',
  'ar': 'AR', 'zh': 'ZH', 'ja': 'JA',
};

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} Ko`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
}

function formatDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

interface DocumentLibraryProps {
  isOpen: boolean;
  onClose: () => void;
  documents: DocMeta[];
  onPreview: (blob: Blob, filename: string, ext: string) => void;
  onDelete: (id: string) => void;
  onClearAll: () => void;
  getBlob: (id: string) => Promise<Blob | undefined>;
}

export default function DocumentLibrary({
  isOpen, onClose, documents, onPreview, onDelete, onClearAll, getBlob,
}: DocumentLibraryProps) {
  const { t } = useTranslation();
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);

  const handlePreview = useCallback(async (doc: DocMeta) => {
    setLoadingId(doc.id);
    try {
      const blob = await getBlob(doc.id);
      if (blob) onPreview(blob, doc.filename, doc.ext);
    } finally {
      setLoadingId(null);
    }
  }, [getBlob, onPreview]);

  const handleDownload = useCallback(async (doc: DocMeta) => {
    setLoadingId(doc.id);
    try {
      const blob = await getBlob(doc.id);
      if (blob) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = doc.filename;
        document.body.appendChild(a);
        a.click();
        URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }
    } finally {
      setLoadingId(null);
    }
  }, [getBlob]);

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            style={{
              position: 'fixed', inset: 0, background: 'rgba(13,27,62,0.35)',
              zIndex: 1100, backdropFilter: 'blur(2px)',
            }}
          />

          {/* Panel */}
          <motion.aside
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 320, damping: 34 }}
            style={{
              position: 'fixed', top: 0, right: 0, bottom: 0,
              width: 'min(420px, 95vw)',
              background: 'var(--white)',
              boxShadow: '-8px 0 40px rgba(13,27,62,0.18)',
              zIndex: 1101,
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
          >
            {/* Header */}
            <div style={{
              padding: '20px 24px 16px',
              borderBottom: '1px solid var(--gray-100)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexShrink: 0,
            }}>
              <div>
                <h2 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--navy)', margin: 0 }}>
                  {t('library.title', 'Mes documents')}
                </h2>
                <p style={{ fontSize: '12px', color: 'var(--gray-500)', margin: '2px 0 0' }}>
                  {documents.length} {t('library.count_suffix', 'document(s) traduit(s)')}
                </p>
              </div>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                {documents.length > 0 && (
                  confirmClear ? (
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button
                        onClick={() => { onClearAll(); setConfirmClear(false); }}
                        style={{ fontSize: '12px', padding: '5px 10px', borderRadius: '6px', border: 'none', background: '#fef2f2', color: '#dc2626', cursor: 'pointer', fontWeight: 600, fontFamily: 'inherit' }}
                      >
                        {t('library.confirm_clear', 'Confirmer')}
                      </button>
                      <button
                        onClick={() => setConfirmClear(false)}
                        style={{ fontSize: '12px', padding: '5px 10px', borderRadius: '6px', border: '1px solid var(--gray-200)', background: 'white', color: 'var(--gray-700)', cursor: 'pointer', fontFamily: 'inherit' }}
                      >
                        {t('library.cancel', 'Annuler')}
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setConfirmClear(true)}
                      style={{ fontSize: '12px', color: 'var(--gray-500)', background: 'none', border: 'none', cursor: 'pointer', padding: '4px 6px', fontFamily: 'inherit' }}
                    >
                      {t('library.clear_all', 'Tout effacer')}
                    </button>
                  )
                )}
                <button
                  onClick={onClose}
                  style={{ width: '32px', height: '32px', borderRadius: '8px', border: 'none', background: 'var(--gray-100)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M18 6L6 18M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Document list */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '12px 16px' }}>
              {documents.length === 0 ? (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  style={{
                    textAlign: 'center', padding: '60px 24px',
                    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px',
                  }}
                >
                  <div style={{ fontSize: '48px', opacity: 0.3 }}>📂</div>
                  <p style={{ color: 'var(--gray-500)', fontSize: '14px', lineHeight: 1.5 }}>
                    {t('library.empty', 'Vos documents traduits apparaîtront ici après chaque traduction.')}
                  </p>
                </motion.div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {documents.map((doc) => (
                    <motion.div
                      key={doc.id}
                      layout
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, x: 20 }}
                      style={{
                        background: 'var(--gray-50)',
                        border: '1px solid var(--gray-200)',
                        borderRadius: '10px',
                        padding: '12px 14px',
                      }}
                    >
                      {/* Row 1: icon + name + lang badge */}
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', marginBottom: '10px' }}>
                        <span style={{ fontSize: '22px', flexShrink: 0, marginTop: '1px' }}>
                          {EXT_ICONS[doc.ext] || '📄'}
                        </span>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <p style={{
                            fontSize: '13px', fontWeight: 600, color: 'var(--navy)',
                            margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                          }}>
                            {doc.filename}
                          </p>
                          <p style={{ fontSize: '11.5px', color: 'var(--gray-500)', margin: '2px 0 0' }}>
                            {formatDate(doc.date)} · {formatSize(doc.sizeByes)}
                          </p>
                        </div>
                        <span style={{
                          fontSize: '11px', fontWeight: 700,
                          background: 'var(--blue-light)', color: 'var(--blue)',
                          padding: '2px 8px', borderRadius: '999px', flexShrink: 0,
                        }}>
                          {LANG_LABELS[doc.targetLang] ?? doc.targetLang.toUpperCase()}
                        </span>
                      </div>

                      {/* Row 2: actions */}
                      <div style={{ display: 'flex', gap: '6px' }}>
                        {doc.ext === 'pdf' && (
                          <button
                            onClick={() => handlePreview(doc)}
                            disabled={loadingId === doc.id}
                            style={{
                              flex: 1, padding: '7px', borderRadius: '7px',
                              border: '1px solid var(--blue)', background: 'white',
                              color: 'var(--blue)', fontSize: '12px', fontWeight: 600,
                              cursor: 'pointer', fontFamily: 'inherit',
                              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px',
                            }}
                          >
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
                            </svg>
                            {t('library.preview', 'Aperçu')}
                          </button>
                        )}
                        <button
                          onClick={() => handleDownload(doc)}
                          disabled={loadingId === doc.id}
                          style={{
                            flex: 1, padding: '7px', borderRadius: '7px',
                            border: 'none', background: 'var(--blue)',
                            color: 'white', fontSize: '12px', fontWeight: 600,
                            cursor: 'pointer', fontFamily: 'inherit',
                            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px',
                          }}
                        >
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M12 5v14" /><path d="M19 12l-7 7-7-7" />
                          </svg>
                          {t('library.download', 'Télécharger')}
                        </button>
                        <button
                          onClick={() => onDelete(doc.id)}
                          style={{
                            width: '34px', padding: '7px', borderRadius: '7px',
                            border: '1px solid var(--gray-200)', background: 'white',
                            color: 'var(--gray-500)', fontSize: '12px',
                            cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                          }}
                          title={t('library.delete', 'Supprimer')}
                        >
                          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6" />
                          </svg>
                        </button>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
