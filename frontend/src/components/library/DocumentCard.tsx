/**
 * Une ligne de la liste « Mes documents » : le document, son état, ses actions.
 *
 * Rendu de la maquette `panneau-compte.html` : le bouton `.open` (aperçu) porte
 * l'icône, le nom, la date et la sous-ligne d'état ; `.acts` porte l'action
 * rapide et le menu « … ».
 *
 * Les états sont mutuellement exclusifs :
 *   • EN COURS  -> pourcentage à la place de la date, pages faites, barre ;
 *   • EN ÉCHEC  -> sous-ligne rouge, lien rapide « Réessayer » ;
 *   • ARRÊTÉ    -> (interrompu, en pause, annulé) lien rapide « Reprendre » ;
 *     les pages déjà faites restent lisibles et téléchargeables ;
 *   • VERROUILLÉ -> (essai, document non réglé) lien rapide « Débloquer » ;
 *   • ARCHIVÉ   -> listé mais fermé : seul « Supprimer » reste possible ;
 *   • terminé   -> date relative, langues, pages ; Télécharger au survol.
 * « Supprimer » reste à sa place dans tous les cas.
 */
import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { motion } from 'motion/react';
import { useTranslation } from 'react-i18next';
import {
  Eye, Download, Trash2, Lock, AlertTriangle, Loader2, RotateCcw, Flag, Pause, X, ScanText,
  FileType2, FileText, Presentation, Sheet, File as FileIcon,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

import { STATUTS_REPRENABLES, type DocMeta } from '../../hooks/useDocumentLibrary';
import type { StopMode } from '../../hooks/useStreamingTranslation';
import { baseCode } from '../../lib/languages';
import { formatDate, formatRelative, formatSize, percent } from '../../lib/format';
import { openSupport } from '../support/supportBus';
import RowMenu, { type RowMenuEntry } from './RowMenu';

const EXT_ICONS: Record<string, LucideIcon> = {
  pdf: FileType2, docx: FileText, pptx: Presentation,
  xlsx: Sheet, txt: FileIcon,
};

// Noms propres de formats, identiques dans toutes les langues ; « Texte » (txt)
// se traduit et passe par `library.ext_text`.
const EXT_NOMS: Record<string, string> = {
  pdf: 'PDF', docx: 'Word', pptx: 'PowerPoint', xlsx: 'Excel',
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
  onStop?: (doc: DocMeta, mode: StopMode) => Promise<void>;
}

/** Sépare « rapport.final.pdf » en [« rapport.final », « .pdf »] : l'extension
 *  reste visible quand le nom est tronqué. */
function scinder(nom: string): [string, string] {
  const i = nom.lastIndexOf('.');
  return i > 0 ? [nom.slice(0, i), nom.slice(i)] : [nom, ''];
}

export default function DocumentCard({
  doc, trial, busy, onPreview, onDownload, onDelete, onRetry, onStop,
}: DocumentCardProps) {
  const { t, i18n } = useTranslation();
  // Arrêt demandé : il prend effet après la page en cours, d'où l'attente.
  const [arret, setArret] = useState<StopMode | null>(null);

  const enCours = doc.status === 'translating';
  // Arrêté (serveur coupé, pause, annulation) : même place et même lien
  // qu'un échec, mais « Reprendre » — les pages faites ne sont pas perdues.
  const arrete = STATUTS_REPRENABLES.includes(doc.status);
  const enErreur = doc.status === 'error' || arrete;
  // Le serveur livre le fichier partiel d'un document arrêté.
  const livrable = arrete && doc.pagesDone > 0;
  const enAttente = doc.status === 'paused' || doc.status === 'cancelled';
  // Repris par une autre traduction (qui porte la suite) : rien à lire ici —
  // sans traduction, le téléchargement servirait l'original.
  const reprise = doc.status === 'resumed';
  // Le droit tient au DOCUMENT, pas au forfait : un compte gratuit qui a réglé
  // ses pages télécharge comme un abonné.
  const verrouille = trial && !doc.paid;
  const archive = doc.archive;

  const termine = !enCours && !enErreur && !reprise;
  const apercuPossible = !archive && !reprise && !(enErreur && !livrable);
  // Terminé mais non réglé : pas d'aperçu, la ligne propose le forfait (le même
  // chemin que « Débloquer »).
  const aDebloquer = termine && verrouille && !archive;

  const demanderArret = (mode: StopMode) => {
    if (!onStop) return;
    setArret(mode);
    onStop(doc, mode).catch(() => setArret(null));
  };

  const Icone = EXT_ICONS[doc.ext] ?? FileIcon;
  const nomFormat = doc.ext === 'txt' ? t('library.ext_text') : (EXT_NOMS[doc.ext] ?? doc.ext.toUpperCase());
  const [base, ext] = scinder(doc.filename);
  const pct = percent(doc.pagesDone, doc.pageCount);

  // Action rapide à la place de la date : le lien le plus utile de l'état.
  let rapide: { label: string; icon: ReactNode; title?: string; onClick: () => void } | null = null;
  if (!archive) {
    if (enErreur && onRetry) {
      rapide = {
        label: t(arrete ? 'library.resume' : 'library.retry'),
        icon: <RotateCcw size={14} strokeWidth={2} aria-hidden="true" />,
        onClick: () => onRetry(doc),
      };
    } else if (termine && verrouille) {
      rapide = {
        label: t('library.unlock'),
        icon: <Lock size={14} strokeWidth={2} aria-hidden="true" />,
        title: t('library.unlock_hint'),
        onClick: () => onDownload(doc),
      };
    }
  }

  const icone = (I: LucideIcon) => <I size={16} strokeWidth={2} className="ic" aria-hidden="true" />;
  const entrees: RowMenuEntry[] = [];
  if (archive) {
    entrees.push({ key: 'supprimer', label: t('library.delete'), icon: icone(Trash2), danger: true, apres: 'ligne', onSelect: () => onDelete(doc.id) });
  } else {
    if (arrete && onRetry) {
      entrees.push({ key: 'reprendre', label: t('library.resume'), icon: icone(RotateCcw), onSelect: () => onRetry(doc) });
    }
    // Pas d'« Aperçu » pendant la traduction, ni sur un document à débloquer.
    if (apercuPossible && !enCours && !aDebloquer) {
      entrees.push({ key: 'apercu', label: t('library.preview'), icon: icone(Eye), apres: 'fenetre', onSelect: () => onPreview(doc) });
    }
    if (termine && !verrouille) {
      entrees.push({ key: 'telecharger', label: t('library.download'), icon: icone(Download), onSelect: () => onDownload(doc) });
    }
    if (livrable && !verrouille) {
      entrees.push({ key: 'partiel', label: t('library.download_partial_menu'), icon: icone(Download), onSelect: () => onDownload(doc) });
    }
    if (enCours && doc.jobId && onStop && arret === null) {
      entrees.push({ key: 'pause', label: t('library.pause'), icon: icone(Pause), onSelect: () => demanderArret('pause') });
      entrees.push({ key: 'annuler', label: t('library.cancel_translation'), icon: icone(X), onSelect: () => demanderArret('cancel') });
    }
    // Signaler un problème SUR CE document : il est référencé automatiquement
    // (id + nom), l'utilisateur n'a rien à retrouver.
    entrees.push({
      key: 'signaler', label: t('library.report_problem'), icon: icone(Flag), apres: 'fenetre',
      onSelect: () => openSupport({ category: 'problem', document: { id: doc.id, name: doc.filename } }),
    });
    entrees.push({ key: 'sep', separator: true });
    entrees.push({ key: 'supprimer', label: t('library.delete'), icon: icone(Trash2), danger: true, apres: 'ligne', onSelect: () => onDelete(doc.id) });
  }

  const separateur = <i aria-hidden="true">·</i>;
  const langues = (() => {
    const cible = baseCode(doc.targetLang).toUpperCase();
    const source = doc.sourceLang && doc.sourceLang !== 'auto' ? baseCode(doc.sourceLang).toUpperCase() : null;
    return source ? `${source} → ${cible}` : `→ ${cible}`;
  })();
  const dateCourte = formatRelative(doc.date, i18n.language, t('library.relative_now'));

  // Sous-ligne : une seule, selon l'état. Les états qui doivent être ANNONCÉS
  // (lecture en cours, échec…) le sont par une région vive posée hors du bouton
  // (`annonce`) : un bouton n'accepte pas de rôle `status` en lui. Seul un
  // CHANGEMENT d'état est annoncé, jamais l'état déjà affiché à l'insertion.
  let sousLigne: ReactNode;
  let annonce: string | null = null;
  if (archive) {
    sousLigne = (
      <>
        <span className="lang">{langues}</span>
        {separateur}
        <span>{t('library.archived_row')}</span>
      </>
    );
  } else if (enCours) {
    sousLigne = (
      <>
        <span className="st st--run">{arret ? t('viewer.stopping') : t('library.status_running')}</span>
        {separateur}
        <span className="tab">{doc.pagesDone}/{doc.pageCount}</span>
      </>
    );
  } else if ((doc.pagesRelues ?? 0) > 0) {
    const texte = t('library.scan_reading', { count: doc.pagesRelues });
    annonce = texte;
    sousLigne = (
      <span className="st st--run">
        <Loader2 size={12} strokeWidth={2.4} className="ui-spin" aria-hidden="true" />
        {texte}
      </span>
    );
  } else if ((doc.pagesADecider ?? 0) > 0) {
    const texte = t('library.scan_to_decide', { count: doc.pagesADecider });
    annonce = texte;
    sousLigne = (
      <span className="st st--run">
        <ScanText size={12} strokeWidth={2.4} aria-hidden="true" />
        {texte}
      </span>
    );
  } else if (reprise) {
    const texte = t('library.resumed_status');
    annonce = texte;
    sousLigne = <span className="st st--run">{texte}</span>;
  } else if (enErreur) {
    const texte = arrete ? t(`library.${doc.status}_status`) : t('library.status_failed');
    annonce = texte;
    sousLigne = (
      <span className={enAttente ? 'st st--run' : 'st st--err'} title={texte}>
        {doc.status === 'paused'
          ? <Pause size={12} strokeWidth={2.4} aria-hidden="true" />
          : <AlertTriangle size={12} strokeWidth={2.4} aria-hidden="true" />}
        {texte}
      </span>
    );
  } else {
    sousLigne = (
      <>
        <span className="lang">{langues}</span>
        {separateur}
        <span className="tab">{t('library.pages_abbr', { count: doc.pageCount })}</span>
        {verrouille && <>{separateur}<span>{dateCourte}</span></>}
        {/* L'état verrouillé n'est sinon dit que par l'icône du lien rapide. */}
        {verrouille && <span className="sr-only">{t('library.unlock_hint')}</span>}
      </>
    );
  }

  // Région vive : vide à l'insertion, remplie seulement quand l'état change.
  const annoncePrecedente = useRef(annonce);
  const [annonceVive, setAnnonceVive] = useState('');
  useEffect(() => {
    if (annonce === annoncePrecedente.current) return;
    annoncePrecedente.current = annonce;
    setAnnonceVive(annonce ?? '');
  }, [annonce]);

  // Date à droite du nom — sauf quand une action rapide ou un archivage prend
  // la place ; en cours, c'est le pourcentage.
  const quand = enCours
    ? <span className="when tab">{new Intl.NumberFormat(i18n.language, { style: 'percent' }).format(pct / 100)}</span>
    : (!rapide && !enErreur && !reprise)
      ? <span className="when" title={formatDate(doc.date, i18n.language)}>{dateCourte}</span>
      : null;

  const classes = ['doc', rapide ? 'doc--quick' : '', archive ? 'doc--archive' : ''].filter(Boolean).join(' ');
  const ouvrable = (apercuPossible || aDebloquer) && !busy;
  // Sous-ligne = description du bouton (son nom reste le nom du fichier) ; elle
  // est masquée au nom pour ne pas être lue deux fois.
  const idSousLigne = `doc-sub-${doc.id}`;

  return (
    <motion.li
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className={classes}
    >
      <button type="button" className="open"
        title={`${doc.filename} — ${formatSize(doc.sizeByes, t)}`}
        aria-describedby={idSousLigne}
        aria-disabled={ouvrable ? undefined : true}
        onClick={ouvrable ? () => (aDebloquer ? onDownload(doc) : onPreview(doc)) : undefined}>
        <span className="ft" title={nomFormat}>
          <Icone size={18} strokeWidth={2} className="ic" aria-hidden="true" />
        </span>
        <span className="t">
          <b>
            <span className="base">{base}</span>
            <span className="ext">{ext}</span>
            {quand}
          </b>
          <span id={idSousLigne} aria-hidden="true">{sousLigne}</span>
          {/* Décorative : la progression est dite par le texte (pages, pourcentage). */}
          {enCours && (
            <span className="prog" aria-hidden="true">
              <i style={{ width: `${pct}%` }} />
            </span>
          )}
        </span>
      </button>
      <span className="sr-only" role="status">{annonceVive}</span>

      <div className="acts">
        {rapide && (
          <button type="button" className="pill" title={rapide.title}
            disabled={busy} onClick={rapide.onClick}>
            {busy
              ? <Loader2 size={14} strokeWidth={2.4} className="ui-spin" aria-hidden="true" />
              : rapide.icon}
            {rapide.label}
          </button>
        )}
        {!rapide && termine && !archive && !verrouille && (
          <button type="button" className="iconbtn hov dl"
            aria-label={t('library.download_named', { name: doc.filename })}
            title={t('library.download')}
            disabled={busy} onClick={() => onDownload(doc)}>
            {busy
              ? <Loader2 size={18} strokeWidth={2.2} className="ui-spin" aria-hidden="true" />
              : <Download size={18} strokeWidth={2} aria-hidden="true" />}
          </button>
        )}
        <RowMenu
          label={t('library.row_options', { name: doc.filename })}
          entries={entrees}
          buttonClassName="hov" />
      </div>
    </motion.li>
  );
}
