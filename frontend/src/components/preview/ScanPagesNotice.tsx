import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ScanText, X } from 'lucide-react';
import type { PageIllisible } from '../../hooks/useDocumentLibrary';

interface Props {
  pages: PageIllisible[];
  /** Pages dont la lecture forcée est en cours : déjà prises en charge. */
  enCours: number[];
  /** Traduction en cours : le choix viendra à la fin. */
  provisoire?: boolean;
  onPageChange: (page: number) => void;
}

/** Message global, au-dessus de l'aperçu : des pages du scan n'ont pas pu être
 *  lues et attendent un choix. Il informe seulement ; la décision se prend sur
 *  la page elle-même. Rien tant que chaque page illisible a un choix. */
export default function ScanPagesNotice({ pages, enCours, provisoire, onPageChange }: Props) {
  const { t } = useTranslation();
  const [masque, setMasque] = useState(false);
  const attente = pages
    // Les pages hors sélection l'ont été à dessein : rien à signaler ici.
    .filter((p) => p.motif !== 'hors_selection' && p.choix === null && !enCours.includes(p.page))
    .map((p) => p.page);
  if (masque || attente.length === 0) return null;

  return (
    <div className="scanp-notice" role="status">
      <ScanText size={14} strokeWidth={2} className="scanp-notice-icon" aria-hidden />
      <span>{t('viewer.scan.notice', { count: attente.length })}</span>
      {attente.map((n) => (
        <button key={n} type="button" className="scanp-chip"
                aria-label={t('viewer.scan.notice_goto', { page: n })}
                onClick={() => onPageChange(n)}>
          {t('viewer.scan.notice_page', { page: n })}
        </button>
      ))}
      <span>{t(provisoire ? 'viewer.scan.notice_wait' : 'viewer.scan.notice_pick')}</span>
      <button type="button" className="scanp-close"
              aria-label={t('viewer.scan.notice_hide')}
              onClick={() => setMasque(true)}>
        <X size={14} aria-hidden />
      </button>
    </div>
  );
}
