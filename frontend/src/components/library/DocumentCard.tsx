/**
 * Une entrée de la bibliothèque : le document, son état, ses actions.
 *
 * Extrait de `DocumentLibrary` — qui en portait le rendu complet, en styles en
 * ligne, au milieu de la logique du panneau. Isolée, la carte se lit d'un
 * écran et son état se raisonne seul : `en cours`, `en erreur`, `verrouillé`,
 * ou rien de tout cela.
 */
import { motion } from 'motion/react';
import { useTranslation } from 'react-i18next';
import {
  Eye, Download, Trash2, Lock, AlertTriangle, Loader2,
  FileType2, FileText, Presentation, File as FileIcon,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

import type { DocMeta } from '../../hooks/useDocumentLibrary';
import { baseCode } from '../../lib/languages';
import { formatDate, formatSize, percent } from '../../lib/format';
import Button from '../ui/Button';
import IconButton from '../ui/IconButton';
import ProgressBar from '../ui/ProgressBar';

const EXT_ICONS: Record<string, LucideIcon> = {
  pdf: FileType2, docx: FileText, pptx: Presentation, txt: FileText,
};

interface DocumentCardProps {
  doc: DocMeta;
  /** Le compte est en essai : le téléchargement dépend alors du document. */
  trial: boolean;
  busy: boolean;
  onPreview: (doc: DocMeta) => void;
  onDownload: (doc: DocMeta) => void;
  onDelete: (id: string) => void;
  onRetry?: (doc: DocMeta) => void;
}

export default function DocumentCard({
  doc, trial, busy, onPreview, onDownload, onDelete, onRetry,
}: DocumentCardProps) {
  const { t, i18n } = useTranslation();

  const enCours = doc.status === 'translating';
  const enErreur = doc.status === 'error';
  // Le droit tient au DOCUMENT, pas au forfait : un compte gratuit qui a réglé
  // ses pages télécharge comme un abonné.
  const verrouille = trial && !doc.paid;

  const Icone = EXT_ICONS[doc.ext] ?? FileIcon;

  const titreTelechargement = enErreur ? t('library.error_status')
    : enCours ? t('library.download_wait')
    : verrouille ? t('library.download_locked')
    : t('library.download');

  return (
    <motion.article
      key={doc.id}
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: 20 }}
      className="doc-carte"
    >
      <header className="doc-carte__tete">
        <span className="doc-carte__icone" aria-hidden><Icone size={17} strokeWidth={2} /></span>
        <div className="doc-carte__ident">
          <p className="doc-carte__nom" title={doc.filename}>{doc.filename}</p>
          <p className="doc-carte__meta">
            {formatDate(doc.date, i18n.language)} · {formatSize(doc.sizeByes, t)}
          </p>
        </div>
        <span className="doc-carte__langue">{baseCode(doc.targetLang).toUpperCase()}</span>
      </header>

      {/* Traduction EN COURS — l'avancement vient de la base, pas du flux : il
          reste donc visible après un rechargement de page ou une reconnexion,
          et le travail continue côté serveur même si personne ne regarde. */}
      {enCours && (
        <div className="doc-carte__avancement">
          <div className="doc-carte__avancement-ligne">
            <span className="doc-carte__etat">
              <Loader2 size={12} strokeWidth={2.4} className="ui-spin" aria-hidden />
              {t('library.translating')}
            </span>
            <span className="doc-carte__compte">{doc.pagesDone}/{doc.pageCount}</span>
          </div>
          <ProgressBar
            value={percent(doc.pagesDone, doc.pageCount)}
            label={t('library.translating')}
          />
        </div>
      )}

      {enErreur && (
        <div className="doc-carte__erreur" role="alert">
          <AlertTriangle size={14} strokeWidth={2.4} aria-hidden />
          <span>{t('library.error_status')}</span>
          {onRetry && (
            <Button variant="danger" size="sm"
              onClick={(e) => { e.stopPropagation(); onRetry(doc); }}>
              {t('library.retry')}
            </Button>
          )}
        </div>
      )}

      <footer className="doc-carte__actions">
        {/* L'aperçu passe par /preview (rastérisé, filigrané pour un essai) —
            JAMAIS par /download, qui rend le PDF en clair. */}
        <Button variant="secondary" size="sm" block
          icon={<Eye size={13} strokeWidth={2.2} />}
          disabled={busy || enErreur}
          onClick={() => onPreview(doc)}>
          {t('library.preview')}
        </Button>

        <Button variant="primary" size="sm" block
          icon={enErreur ? <AlertTriangle size={13} strokeWidth={2.2} />
            : verrouille ? <Lock size={13} strokeWidth={2.2} />
            : <Download size={13} strokeWidth={2.2} />}
          loading={busy}
          disabled={enCours || enErreur}
          title={titreTelechargement}
          onClick={() => onDownload(doc)}>
          {enErreur ? t('library.error_status')
            : enCours ? t('library.in_progress')
            : verrouille ? t('library.unlock')
            : t('library.download')}
        </Button>

        <IconButton label={t('library.delete')} variant="danger" size="md"
          onClick={() => onDelete(doc.id)}>
          <Trash2 size={14} strokeWidth={2.2} />
        </IconButton>
      </footer>
    </motion.article>
  );
}
