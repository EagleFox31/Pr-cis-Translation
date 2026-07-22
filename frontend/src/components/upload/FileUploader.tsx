import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { motion, AnimatePresence } from 'motion/react';
import { UploadCloud, FileText, FileType2, Presentation, Sheet, File as FileIcon, X, AlertCircle } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

interface FileUploaderProps {
  selectedFile: File | null;
  onFileSelect: (file: File | null) => void;
  disabled?: boolean;
}

const ACCEPTED = ['pdf', 'docx', 'pptx', 'xlsx', 'txt'] as const;
const MAX_BYTES = 100 * 1024 * 1024;

/** Hauteur commune aux deux états de la zone (vide / document choisi). Sans
 *  elle, la zone de dépôt (~180px) laissait place à une fiche compacte (~66px)
 *  et TOUT le formulaire situé en dessous remontait d'un coup — le contenu
 *  semblait « sauter » au moment du choix du fichier. */
const ZONE_HEIGHT = 168;

const EXT_ICONS: Record<string, LucideIcon> = {
  pdf: FileType2,
  docx: FileText,
  pptx: Presentation,
  xlsx: Sheet,
  txt: FileText,
};

export default function FileUploader({ selectedFile, onFileSelect, disabled }: FileUploaderProps) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} ${t('units.b')}`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} ${t('units.kb')}`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} ${t('units.mb')}`;
  };

  // Les erreurs s'affichent SOUS le champ (rattachées via aria-describedby)
  // plutôt que dans un alert() bloquant, qui sort du flux et n'est pas annoncé
  // comme une erreur de formulaire aux lecteurs d'écran.
  const accept = (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
    if (!ACCEPTED.includes(ext as (typeof ACCEPTED)[number])) {
      setError(t('story.error_unsupported'));
      return;
    }
    if (file.size > MAX_BYTES) {
      setError(t('story.error_too_large'));
      return;
    }
    setError(null);
    onFileSelect(file);
  };

  const openPicker = () => {
    if (!disabled) inputRef.current?.click();
  };

  if (selectedFile) {
    const ext = selectedFile.name.split('.').pop()?.toLowerCase() ?? '';
    const Icon = EXT_ICONS[ext] ?? FileIcon;
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.99 }}
        animate={{ opacity: 1, scale: 1 }}
        style={{
          position: 'relative',
          height: `${ZONE_HEIGHT}px`, boxSizing: 'border-box',
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: '4px',
          padding: '16px', borderRadius: '12px',
          border: '1.5px solid #dbeafe', background: '#eff6ff',
        }}
      >
        <button
          type="button"
          onClick={() => { onFileSelect(null); setError(null); }}
          disabled={disabled}
          aria-label={t('story.remove_file')}
          style={{
            position: 'absolute', top: '10px', right: '10px',
            display: 'flex', alignItems: 'center',
            background: 'none', border: 'none', color: 'var(--gray-400)',
            cursor: disabled ? 'not-allowed' : 'pointer',
            padding: '5px', borderRadius: '7px', transition: 'all 0.15s',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = '#dbeafe'; e.currentTarget.style.color = 'var(--gray-700)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--gray-400)'; }}
        >
          <X size={15} strokeWidth={2.2} />
        </button>

        <span style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          width: '44px', height: '44px', borderRadius: '11px', marginBottom: '6px',
          background: 'var(--white)', border: '1px solid #dbeafe', color: 'var(--blue)',
        }}>
          <Icon size={21} strokeWidth={1.9} />
        </span>

        <p style={{
          maxWidth: '100%', margin: 0, padding: '0 24px',
          fontSize: '14px', fontWeight: 600, color: 'var(--navy)', textAlign: 'center',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {selectedFile.name}
        </p>
        <p style={{
          margin: 0, fontSize: '12px', color: 'var(--gray-500)',
          fontFamily: 'var(--font-mono)', textTransform: 'uppercase',
        }}>
          {ext} · {formatSize(selectedFile.size)}
        </p>

        <button
          type="button"
          onClick={openPicker}
          disabled={disabled}
          style={{
            marginTop: '8px', padding: '5px 12px', borderRadius: '7px',
            border: '1px solid #bfdbfe', background: 'var(--white)',
            color: 'var(--blue)', fontSize: '12px', fontWeight: 600,
            fontFamily: 'inherit', cursor: disabled ? 'not-allowed' : 'pointer',
          }}
        >
          {t('story.replace_file')}
        </button>

        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.pptx,.xlsx,.txt"
          hidden
          disabled={disabled}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) accept(f);
            e.target.value = '';
          }}
        />
      </motion.div>
    );
  }

  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx,.pptx,.xlsx,.txt"
        hidden
        disabled={disabled}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) accept(f);
          e.target.value = '';   // re-choisir le MÊME fichier doit redéclencher change
        }}
      />

      {/* Zone de dépôt — role=button + tabIndex : atteignable et actionnable au
          clavier (Entrée / Espace), ce qu'un <div onClick> ne permet pas. */}
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-disabled={disabled}
        aria-describedby={error ? 'file-error' : undefined}
        onClick={openPicker}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openPicker(); }
        }}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          if (disabled) return;
          const f = e.dataTransfer.files[0];
          if (f) accept(f);
        }}
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        style={{
          height: `${ZONE_HEIGHT}px`, boxSizing: 'border-box',
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          border: `2px dashed ${error ? '#fca5a5' : isDragging ? 'var(--blue)' : 'var(--color-border-primary)'}`,
          background: error ? '#fef7f7' : isDragging ? 'var(--blue-light)' : 'var(--color-background-secondary)',
          borderRadius: '12px',
          padding: '16px 20px',
          textAlign: 'center',
          cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.6 : 1,
          transition: 'border-color 0.2s, background 0.2s',
          outlineOffset: '2px',
        }}
      >
        <motion.div
          animate={isDragging ? { y: -4 } : { y: 0 }}
          style={{
            display: 'flex', justifyContent: 'center', marginBottom: '8px',
            color: isDragging ? 'var(--blue)' : 'var(--gray-500)',
          }}
        >
          <UploadCloud size={34} strokeWidth={1.5} />
        </motion.div>

        <p style={{
          margin: 0, fontSize: '14px', fontWeight: 600,
          color: isDragging ? 'var(--blue)' : 'var(--navy)',
        }}>
          {isDragging ? t('story.drop_ready') : t('story.drop_text')}
        </p>
        <p
          style={{ margin: '4px 0 0', fontSize: '13px', color: 'var(--gray-500)' }}
          dangerouslySetInnerHTML={{ __html: t('story.browse_text') }}
        />

        <div style={{ display: 'flex', gap: '6px', justifyContent: 'center', marginTop: '12px' }}>
          {ACCEPTED.map((fmt) => (
            <span
              key={fmt}
              style={{
                fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 500,
                padding: '3px 8px', borderRadius: '4px',
                background: 'var(--gray-100)', color: 'var(--gray-500)',
                border: '1px solid var(--gray-200)', textTransform: 'uppercase',
              }}
            >
              {fmt}
            </span>
          ))}
        </div>
      </div>

      <AnimatePresence>
        {error && (
          <motion.p
            id="file-error"
            role="alert"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              marginTop: '8px', fontSize: '12.5px', color: '#dc2626',
            }}
          >
            <AlertCircle size={14} strokeWidth={2.2} style={{ flexShrink: 0 }} />
            {error}
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  );
}
