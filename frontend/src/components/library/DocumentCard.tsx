/**
 * Une entrée de la bibliothèque : le document, son état, ses actions.
 *
 * OBJET RECONSTRUIT (`libdoc`)
 * ----------------------------
 * L'ancien objet (`doc-carte`) affichait chez un utilisateur une barre d'actions
 * anormalement haute et sombre qu'aucune règle du dépôt n'expliquait — un résidu
 * introuvable, insensible au redémarrage du serveur. On est repartis de zéro
 * avec des classes INÉDITES (`libdoc`) : aucune règle ancienne ou parasite ne
 * peut plus les cibler. Structure identique, tailles normales garanties.
 *
 * La carte a trois états mutuellement exclusifs sous l'en-tête :
 *   • EN COURS  -> barre d'avancement (pages faites / total) ;
 *   • EN ERREUR -> ligne d'alerte, et le bouton central devient « Réessayer » ;
 *   • terminé   -> Aperçu + Télécharger.
 * Le bouton Supprimer reste à sa place dans tous les cas.
 */
import { motion } from 'motion/react';
import { useTranslation } from 'react-i18next';
import {
  Eye, Download, Trash2, Lock, AlertTriangle, Loader2, RotateCcw, Flag,
  FileType2, FileText, Presentation, Sheet, File as FileIcon,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

import type { DocMeta } from '../../hooks/useDocumentLibrary';
import { baseCode } from '../../lib/languages';
import { formatDate, formatSize, percent } from '../../lib/format';
import Button from '../ui/Button';
import IconButton from '../ui/IconButton';
import ProgressBar from '../ui/ProgressBar';
import { openSupport } from '../support/supportBus';

const EXT_ICONS: Record<string, LucideIcon> = {
  pdf: FileType2, docx: FileText, pptx: Presentation,
  xlsx: Sheet, txt: FileText,
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

  const titreTelechargement = enCours ? t('library.download_wait')
    : verrouille ? t('library.download_locked')
    : t('library.download');

  return (
    <motion.article
      key={doc.id}
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: 20 }}
      className="libdoc"
    >
      <div className="libdoc__head">
        <span className="libdoc__icon" aria-hidden><Icone size={17} strokeWidth={2} /></span>
        <div className="libdoc__ident">
          <p className="libdoc__name" title={doc.filename}>{doc.filename}</p>
          <p className="libdoc__meta">
            {formatDate(doc.date, i18n.language)} · {formatSize(doc.sizeByes, t)}
          </p>
        </div>
        <span className="libdoc__lang">{baseCode(doc.targetLang).toUpperCase()}</span>
      </div>

      {/* EN COURS — l'avancement vient de la base : il survit à un rechargement
          de page, et le travail continue côté serveur même si personne ne
          regarde. */}
      {enCours && (
        <div className="libdoc__progress">
          <div className="libdoc__progress-row">
            <span className="libdoc__state">
              <Loader2 size={12} strokeWidth={2.4} className="ui-spin" aria-hidden />
              {t('library.translating')}
            </span>
            <span className="libdoc__count">{doc.pagesDone}/{doc.pageCount}</span>
          </div>
          <ProgressBar
            value={percent(doc.pagesDone, doc.pageCount)}
            label={t('library.translating')}
          />
        </div>
      )}

      {/* EN ERREUR — ligne d'alerte ; le « Réessayer » est dans la barre d'actions
          (à la place du Télécharger), pas ici. */}
      {enErreur && (
        <div className="libdoc__error" role="alert">
          <AlertTriangle size={14} strokeWidth={2.4} aria-hidden />
          <span>{t('library.error_status')}</span>
        </div>
      )}

      {/* Zone d'action, hauteur naturelle. Le fond transparent est aussi posé
          EN LIGNE : blindage définitif contre toute règle qui tenterait de la
          colorer, quelle qu'en soit l'origine. */}
      <div className="libdoc__actions" style={{ background: 'transparent' }}>
        <Button variant="secondary" size="sm" block
          icon={<Eye size={13} strokeWidth={2.2} />}
          disabled={busy || enErreur}
          onClick={() => onPreview(doc)}>
          {t('library.preview')}
        </Button>

        {/* Échec → « Réessayer » au MÊME emplacement que Télécharger. */}
        {enErreur && onRetry ? (
          <Button variant="primary" size="sm" block
            icon={<RotateCcw size={13} strokeWidth={2.2} />}
            loading={busy}
            onClick={() => onRetry(doc)}>
            {t('library.retry')}
          </Button>
        ) : (
          <Button variant="primary" size="sm" block
            icon={verrouille ? <Lock size={13} strokeWidth={2.2} />
              : <Download size={13} strokeWidth={2.2} />}
            loading={busy}
            disabled={enCours || enErreur}
            title={titreTelechargement}
            onClick={() => onDownload(doc)}>
            {enCours ? t('library.in_progress')
              : verrouille ? t('library.unlock')
              : t('library.download')}
          </Button>
        )}

        {/* Signaler un problème SUR CE document : le document est référencé
            automatiquement (id + nom), l'utilisateur n'a rien à retrouver. */}
        <IconButton label={t('support.report', 'Signaler un problème')} variant="neutral" size="md"
          onClick={() => openSupport({ category: 'problem', document: { id: doc.id, name: doc.filename } })}>
          <Flag size={14} strokeWidth={2.2} />
        </IconButton>

        <IconButton label={t('library.delete')} variant="danger" size="md"
          onClick={() => onDelete(doc.id)}>
          <Trash2 size={14} strokeWidth={2.2} />
        </IconButton>
      </div>
    </motion.article>
  );
}
