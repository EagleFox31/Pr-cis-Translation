import { motion } from 'motion/react';
import PdfViewer from './PdfViewer';
import { usePdfPreview } from '../../hooks/usePdfPreview';

interface DocumentPreviewProps {
  sourceFile?: File | null;
  translatedBlob?: Blob | null;
  /** Format du document (pdf, docx, pptx, txt). */
  ext: string;
  currentPage: number;
  zoom: number;
  isTrialMode: boolean;
  onPagesLoaded?: (numPages: number) => void;
  /** La page courante est-elle déjà traduite (streaming page par page) ? */
  translatedPageReady?: boolean;
  /** Statut de la page courante côté traduction (pour le placeholder). */
  translatedPageStatus?: string;
}

/**
 * Aperçu unifié pour tous les formats. Les formats non-PDF (DOCX, PPTX, TXT)
 * sont convertis en PDF côté serveur (LibreOffice) pour un rendu EXACT, puis
 * affichés avec le même viewer pdf.js que les PDF natifs.
 */
export default function DocumentPreview({
  sourceFile,
  translatedBlob,
  ext,
  currentPage,
  zoom,
  isTrialMode,
  onPagesLoaded,
  translatedPageReady = true,
  translatedPageStatus,
}: DocumentPreviewProps) {
  const { sourcePdf, translatedPdf, loading, error } = usePdfPreview(sourceFile, translatedBlob, ext);

  if (loading) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '14px',
          minHeight: '300px',
          width: '100%',
          color: 'var(--color-text-secondary)',
        }}
      >
        <motion.span
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
          style={{ display: 'inline-flex' }}
        >
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <circle cx="12" cy="12" r="10" opacity="0.25" />
            <path d="M12 2a10 10 0 0 1 10 10" strokeLinecap="round" />
          </svg>
        </motion.span>
        <span style={{ fontSize: '13px' }}>Préparation de l’aperçu…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '8px',
          minHeight: '300px',
          width: '100%',
          padding: '24px',
          textAlign: 'center',
          color: '#dc2626',
        }}
      >
        <span style={{ fontSize: '24px' }}>⚠</span>
        <span style={{ fontSize: '13px' }}>Aperçu indisponible : {error}</span>
        <span style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>
          Le document traduit reste téléchargeable.
        </span>
      </div>
    );
  }

  return (
    <PdfViewer
      sourceFile={sourcePdf}
      translatedBlob={translatedPdf}
      currentPage={currentPage}
      zoom={zoom}
      isTrialMode={isTrialMode}
      onPagesLoaded={onPagesLoaded}
      translatedPageReady={translatedPageReady}
      translatedPageStatus={translatedPageStatus}
    />
  );
}
