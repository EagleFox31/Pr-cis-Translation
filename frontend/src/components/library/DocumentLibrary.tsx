import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import {
  X, Eye, Download, Trash2, FolderOpen,
  FileType2, FileText, Presentation, File as FileIcon,
  LogOut, Crown, HardDrive, Mail, User,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { TFunction } from 'i18next';
import type { DocMeta } from '../../hooks/useDocumentLibrary';
import { useAuth, type AuthUser } from '../../contexts/AuthContext';
import { baseCode } from '../../lib/languages';

const EXT_ICONS: Record<string, LucideIcon> = {
  pdf: FileType2, docx: FileText, pptx: Presentation, txt: FileText,
};

const PLAN_LABELS: Record<string, string> = {
  free: 'Gratuit', starter: 'Starter', pro: 'Pro', enterprise: 'Enterprise', admin: 'Admin',
};

function formatSize(bytes: number, t: TFunction) {
  if (bytes < 1024) return `${bytes} ${t('units.b')}`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} ${t('units.kb')}`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} ${t('units.mb')}`;
}

function formatDate(iso: string, locale: string) {
  const d = new Date(iso);
  return new Date(d).toLocaleDateString(locale, { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function formatBytes(bytes: number): string {
  if (bytes >= 1_073_741_824) return `${(bytes / 1_073_741_824).toFixed(1)} Go`;
  if (bytes >= 1_048_576) return `${(bytes / 1_048_576).toFixed(0)} Mo`;
  return `${(bytes / 1024).toFixed(0)} Ko`;
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
  const { t, i18n } = useTranslation();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);

  const handlePreview = useCallback(async (doc: DocMeta) => {
    setLoadingId(doc.id);
    try { const blob = await getBlob(doc.id); if (blob) onPreview(blob, doc.filename, doc.ext); }
    finally { setLoadingId(null); }
  }, [getBlob, onPreview]);

  const handleDownload = useCallback(async (doc: DocMeta) => {
    setLoadingId(doc.id);
    try {
      const blob = await getBlob(doc.id);
      if (blob) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a'); a.href = url; a.download = doc.filename;
        document.body.appendChild(a); a.click();
        URL.revokeObjectURL(url); document.body.removeChild(a);
      }
    } finally { setLoadingId(null); }
  }, [getBlob]);

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={onClose}
            style={{ position: 'fixed', inset: 0, background: 'rgba(13,27,62,0.35)', zIndex: 1100, backdropFilter: 'blur(2px)' }}
          />

          <motion.aside
            initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 320, damping: 34 }}
            style={{
              position: 'fixed', top: 0, right: 0, bottom: 0,
              width: 'min(420px, 95vw)', background: 'white',
              boxShadow: '-8px 0 40px rgba(13,27,62,0.18)', zIndex: 1101,
              display: 'flex', flexDirection: 'column', overflow: 'hidden',
            }}
          >
            {/* ═══ PROFIL (connecté uniquement) ═══ */}
            {user && <ProfileSection user={user} onClose={onClose} onLogout={logout} navigate={navigate} />}

            {/* ═══ DOCUMENTS ═══ */}
            <div style={{ padding: user ? '0 24px' : '20px 24px 16px', borderBottom: '1px solid var(--gray-100)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
              <div>
                <h2 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--navy)', margin: 0 }}>
                  {t('library.title', 'Mes documents')}
                </h2>
                <p style={{ fontSize: '12px', color: 'var(--gray-500)', margin: '2px 0 0' }}>
                  {documents.length} {t('library.count_suffix', 'document(s)')}
                </p>
              </div>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                {documents.length > 0 && (
                  confirmClear ? (
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button onClick={() => { onClearAll(); setConfirmClear(false); }}
                        style={{ fontSize: '12px', padding: '5px 10px', borderRadius: '6px', border: 'none', background: '#fef2f2', color: '#dc2626', cursor: 'pointer', fontWeight: 600, fontFamily: 'inherit' }}>{t('library.confirm_clear', 'Confirmer')}</button>
                      <button onClick={() => setConfirmClear(false)}
                        style={{ fontSize: '12px', padding: '5px 10px', borderRadius: '6px', border: '1px solid var(--gray-200)', background: 'white', color: 'var(--gray-700)', cursor: 'pointer', fontFamily: 'inherit' }}>{t('library.cancel', 'Annuler')}</button>
                    </div>
                  ) : (
                    <button onClick={() => setConfirmClear(true)}
                      style={{ fontSize: '12px', color: 'var(--gray-500)', background: 'none', border: 'none', cursor: 'pointer', padding: '4px 6px', fontFamily: 'inherit' }}>{t('library.clear_all', 'Tout effacer')}</button>
                  )
                )}
                <button onClick={onClose}
                  style={{ width: '32px', height: '32px', borderRadius: '8px', border: 'none', background: 'var(--gray-100)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <X size={16} strokeWidth={2.2} />
                </button>
              </div>
            </div>

            {/* Document list */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '12px 16px' }}>
              {documents.length === 0 ? (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                  style={{ textAlign: 'center', padding: '60px 24px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
                  <FolderOpen size={44} strokeWidth={1.4} style={{ color: 'var(--gray-400)', opacity: 0.6 }} />
                  <p style={{ color: 'var(--gray-500)', fontSize: '14px', lineHeight: 1.5 }}>
                    {user
                      ? t('library.empty', 'Vos documents traduits apparaîtront ici après chaque traduction.')
                      : 'Connectez-vous pour sauvegarder vos traductions.'}
                  </p>
                  {!user && (
                    <button onClick={() => { onClose(); navigate('/login'); }}
                      style={{ marginTop: '8px', padding: '8px 20px', borderRadius: '8px', border: 'none', background: 'var(--blue)', color: 'white', fontWeight: 600, fontSize: '13px', cursor: 'pointer', fontFamily: 'inherit' }}>
                      Se connecter
                    </button>
                  )}
                </motion.div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {documents.map((doc) => (
                    <motion.div key={doc.id} layout initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, x: 20 }}
                      style={{ background: 'var(--gray-50)', border: '1px solid var(--gray-200)', borderRadius: '10px', padding: '12px 14px' }}>
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', marginBottom: '10px' }}>
                        <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '34px', height: '34px', borderRadius: '9px', flexShrink: 0, background: 'white', border: '1px solid var(--gray-200)', color: 'var(--blue)' }}>
                          {(() => { const Icon = EXT_ICONS[doc.ext] ?? FileIcon; return <Icon size={17} strokeWidth={2} />; })()}
                        </span>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <p style={{ fontSize: '13px', fontWeight: 600, color: 'var(--navy)', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{doc.filename}</p>
                          <p style={{ fontSize: '11.5px', color: 'var(--gray-500)', margin: '2px 0 0' }}>{formatDate(doc.date, i18n.language)} · {formatSize(doc.sizeByes, t)}</p>
                        </div>
                        <span style={{ fontSize: '11px', fontWeight: 700, background: 'var(--blue-light)', color: 'var(--blue)', padding: '2px 8px', borderRadius: '999px', flexShrink: 0 }}>{baseCode(doc.targetLang).toUpperCase()}</span>
                      </div>
                      <div style={{ display: 'flex', gap: '6px' }}>
                        {doc.ext === 'pdf' && (
                          <button onClick={() => handlePreview(doc)} disabled={loadingId === doc.id}
                            style={{ flex: 1, padding: '7px', borderRadius: '7px', border: '1px solid var(--blue)', background: 'white', color: 'var(--blue)', fontSize: '12px', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px' }}>
                            <Eye size={13} strokeWidth={2.2} />{t('library.preview', 'Aperçu')}
                          </button>
                        )}
                        <button onClick={() => handleDownload(doc)} disabled={loadingId === doc.id}
                          style={{ flex: 1, padding: '7px', borderRadius: '7px', border: 'none', background: 'var(--blue)', color: 'white', fontSize: '12px', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px' }}>
                          <Download size={13} strokeWidth={2.2} />{t('library.download', 'Télécharger')}
                        </button>
                        <button onClick={() => onDelete(doc.id)}
                          style={{ width: '34px', padding: '7px', borderRadius: '7px', border: '1px solid var(--gray-200)', background: 'white', color: 'var(--gray-500)', fontSize: '12px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }} title={t('library.delete', 'Supprimer')}>
                          <Trash2 size={14} strokeWidth={2.2} />
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

/** Bloc profil dans la sidebar — affiché uniquement quand l'utilisateur est connecté. */
function ProfileSection({ user, onClose, onLogout, navigate }: {
  user: AuthUser;
  onClose: () => void;
  onLogout: () => Promise<void>;
  navigate: (path: string) => void;
}) {
  const avatar = user.name ? user.name[0].toUpperCase() : (user.email?.[0].toUpperCase() || '?');

  return (
    <div style={{
      padding: '24px 24px 20px', borderBottom: '1px solid var(--gray-100)', flexShrink: 0,
      background: 'linear-gradient(160deg, #f8fafc 0%, #eef2ff 100%)',
    }}>
      {/* Avatar + nom */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
        <div style={{
          width: '44px', height: '44px', borderRadius: '999px',
          background: 'var(--blue)', color: 'white', fontWeight: 700, fontSize: '18px',
          display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
        }}>{avatar}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--gray-900)' }}>
            {user.name || 'Utilisateur'}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px', color: 'var(--gray-500)', marginTop: '1px' }}>
            <Mail size={11} /> {user.email}
          </div>
        </div>
        <span style={{
          background: user.plan === 'free' ? 'var(--gray-100)' : 'var(--blue-light)',
          color: user.plan === 'free' ? 'var(--gray-500)' : 'var(--blue)',
          fontSize: '10px', fontWeight: 700, padding: '3px 8px', borderRadius: '6px',
          textTransform: 'uppercase', letterSpacing: '0.04em',
        }}>{PLAN_LABELS[user.plan] || user.plan}</span>
      </div>

      {/* Stockage */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px',
        padding: '10px 12px', borderRadius: '10px', background: 'white',
        border: '1px solid var(--gray-100)',
      }}>
        <HardDrive size={15} style={{ color: 'var(--gray-400)', flexShrink: 0 }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          {user.storage_limit > 0 ? (
            <>
              <div style={{ fontSize: '12px', color: 'var(--gray-600)', marginBottom: '3px' }}>
                {formatBytes(user.storage_used)} / {formatBytes(user.storage_limit)}
              </div>
              <div style={{ height: '3px', background: 'var(--gray-100)', borderRadius: '2px' }}>
                <div style={{
                  height: '3px', borderRadius: '2px', background: 'var(--blue)',
                  width: `${Math.min(100, (user.storage_used / user.storage_limit) * 100)}%`,
                  transition: 'width 0.3s ease',
                }} />
              </div>
            </>
          ) : user.plan === 'admin' ? (
            <div style={{ fontSize: '12px', color: 'var(--gray-600)' }}>
              <Crown size={12} style={{ marginRight: '4px', verticalAlign: 'middle', color: '#ca8a04' }} />
              {formatBytes(user.storage_used)} · Illimité
            </div>
          ) : (
            <div style={{ fontSize: '12px', color: 'var(--gray-400)', fontStyle: 'italic' }}>
              Traduction seule — sans stockage
            </div>
          )}
        </div>
      </div>

      {/* Déconnexion */}
      <button
        onClick={async () => { onClose(); await onLogout(); }}
        style={{
          width: '100%', marginTop: '12px', display: 'flex', alignItems: 'center',
          justifyContent: 'center', gap: '6px', padding: '8px', borderRadius: '8px',
          border: '1px solid var(--gray-200)', background: 'white',
          color: 'var(--gray-500)', fontSize: '12px', fontWeight: 500,
          cursor: 'pointer', fontFamily: 'inherit', transition: 'all 0.15s',
        }}
        onMouseEnter={e => { e.currentTarget.style.color = '#dc2626'; e.currentTarget.style.borderColor = '#fecaca'; e.currentTarget.style.background = '#fef2f2'; }}
        onMouseLeave={e => { e.currentTarget.style.color = 'var(--gray-500)'; e.currentTarget.style.borderColor = 'var(--gray-200)'; e.currentTarget.style.background = 'white'; }}
      >
        <LogOut size={14} /> Déconnexion
      </button>
    </div>
  );
}
