/**
 * Téléchargement d'une traduction qui a des pages libres (non payées).
 *
 * Au clic sur « Télécharger », le solde paie d'office ce qu'il peut (quota du
 * forfait, puis pages achetées). S'il reste des pages non payées, une fenêtre
 * propose de les acheter ou de continuer avec un fichier limité aux pages
 * payées. Partagé par la bibliothèque et l'accueil.
 */
import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { X } from 'lucide-react';

import { authFetch } from '../../services/api';
import { signalerStockageRequis } from '../../hooks/useDocumentLibrary';
import Button from '../ui/Button';
import { showToast } from '../ui/Toast';
import PaymentModal from '../payment/LazyPaymentModal';
import '../nouveautes/modal.css';

interface Reglement { pages_debitees: number; pages_libres: number; paid: boolean }
interface Choix { id: string; filename: string; debitees: number; libres: number; continuable: boolean }

/** `ok` : fichier remis ; `libres` : la fenêtre a pris la main ; `echec` : rien. */
export type IssueTelechargement = 'ok' | 'libres' | 'echec';

function enregistrer(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

/** Même suffixe que le nom donné par le serveur au fichier partiel. */
const nomPartiel = (filename: string) => filename.replace(/(\.[^.]+)?$/, '_PARTIEL$1');

async function pagesLibresRefusees(res: Response): Promise<boolean> {
  if (res.status !== 402) return false;
  try {
    return (await res.clone().json())?.reason === 'pages_libres';
  } catch {
    return false;
  }
}

/**
 * `onChange` : un solde ou un document a changé (liste à recharger).
 * `onRegle` : pages encore libres d'un document après un règlement (l'aperçu
 * en cours peut mettre sa ligne « N pages en aperçu » à jour).
 */
export function useTelechargementLibres(
  onChange?: () => void,
  onRegle?: (id: string, pagesLibres: number) => void,
) {
  const { t } = useTranslation();
  const [choix, setChoix] = useState<Choix | null>(null);
  const [achat, setAchat] = useState<
    { id: string; filename: string; pages: number; telecharger: boolean } | null
  >(null);

  /** Le solde paie ce qu'il peut ; `null` si la requête a échoué. */
  const regler = useCallback(async (id: string): Promise<Reglement | null> => {
    const regle = await authFetch(`/api/documents/${id}/regler-libres`, { method: 'POST' });
    if (!regle.ok) return null;
    const r: Reglement = await regle.json();
    // Rien de débité : rien n'a changé, l'aperçu n'a pas à être rechargé.
    if (r.pages_debitees > 0) {
      onChange?.();
      onRegle?.(id, r.pages_libres);
    }
    return r;
  }, [onChange, onRegle]);

  const telecharger = useCallback(async (
    id: string, filename: string, sansLibres = false,
  ): Promise<IssueTelechargement> => {
    const url = `/api/documents/${id}/download${sansLibres ? '?sans_libres=1' : ''}`;
    try {
      let res = await authFetch(url);
      if (!sansLibres && await pagesLibresRefusees(res)) {
        const r = await regler(id);
        if (!r) { showToast('error', t('libre_download.error')); return 'echec'; }
        if (r.pages_libres > 0) {
          setChoix({ id, filename, debitees: r.pages_debitees, libres: r.pages_libres, continuable: r.paid });
          return 'libres';
        }
        showToast('success', t('libre_download.debited_toast', { count: r.pages_debitees }));
        res = await authFetch(url);
      }
      if (!res.ok) {
        // 403 « stockage requis » : message dédié ; tout autre refus : message générique.
        if (!(await signalerStockageRequis(res))) showToast('error', t('libre_download.error'));
        return 'echec';
      }
      // Nom donné par le serveur : il sait si le fichier est partiel (arrêt).
      const partiel = res.headers.get('content-disposition')?.includes('_PARTIEL') ?? sansLibres;
      enregistrer(await res.blob(), partiel ? nomPartiel(filename) : filename);
      return 'ok';
    } catch {
      showToast('error', t('libre_download.error'));
      return 'echec';
    }
  }, [regler, t]);

  /**
   * Achat des pages libres depuis l'aperçu. Le solde paie d'abord ce qu'il
   * peut (il a pu grossir depuis la traduction) : on ne fait payer que le reste.
   * Après paiement, le solde règle les pages achetées.
   */
  const acheterLibres = useCallback(async (id: string, filename: string) => {
    let r: Reglement | null = null;
    try { r = await regler(id); } catch { r = null; }
    if (!r) { showToast('error', t('libre_download.error')); return; }
    if (r.pages_debitees > 0) {
      showToast('success', t('libre_download.debited_toast', { count: r.pages_debitees }));
    }
    if (r.pages_libres > 0) {
      setAchat({ id, filename, pages: r.pages_libres, telecharger: false });
    }
  }, [regler, t]);

  const continuer = useCallback(() => {
    if (!choix) return;
    setChoix(null);
    void telecharger(choix.id, choix.filename, true);
  }, [choix, telecharger]);

  const acheter = useCallback(() => {
    if (!choix) return;
    setAchat({ id: choix.id, filename: choix.filename, pages: choix.libres, telecharger: true });
    setChoix(null);
  }, [choix]);

  const fenetre = (
    <>
      {choix && (
        <FenetreLibres choix={choix} onAcheter={acheter} onContinuer={continuer} onClose={() => setChoix(null)} />
      )}
      <PaymentModal
        open={!!achat}
        onClose={() => setAchat(null)}
        pages={achat?.pages ?? 1}
        label={t('libre_download.buy_label', { count: achat?.pages ?? 1 })}
        onPaid={() => {
          // Pages achetées : le règlement d'office les prend, le fichier est complet.
          const a = achat;
          setAchat(null);
          onChange?.();
          if (!a) return;
          if (a.telecharger) { void telecharger(a.id, a.filename); return; }
          void regler(a.id).then((r) => {
            if (!r) showToast('error', t('libre_download.error'));
            else if (r.pages_debitees > 0) {
              showToast('success', t('libre_download.debited_toast', { count: r.pages_debitees }));
            }
          }).catch(() => showToast('error', t('libre_download.error')));
        }}
      />
    </>
  );

  return { telecharger, acheterLibres, fenetre };
}

function FenetreLibres({ choix, onAcheter, onContinuer, onClose }: {
  choix: Choix; onAcheter: () => void; onContinuer: () => void; onClose: () => void;
}) {
  const { t } = useTranslation();
  const uid = useId();
  const boite = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Focus sur l'action principale (« Acheter »), dernier bouton de la fenêtre.
    boite.current?.querySelector<HTMLButtonElement>('.ui-btn:last-of-type')?.focus();
    const echap = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', echap);
    return () => window.removeEventListener('keydown', echap);
  }, [onClose]);

  return createPortal(
    <>
      <div className="nv-veil" onClick={onClose} aria-hidden="true" />
      <div
        ref={boite}
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${uid}-t`}
        aria-describedby={`${uid}-d`}
        className="nvd tl-fenetre"
      >
        <button type="button" className="nvd__x" onClick={onClose} aria-label={t('libre_download.close')}>
          <X size={18} aria-hidden="true" />
        </button>
        <div className="nvd__head">
          <h2 id={`${uid}-t`}>{t('libre_download.title', { count: choix.libres })}</h2>
        </div>
        <div id={`${uid}-d`} className="tl-fenetre__texte">
          {choix.debitees > 0 && <p>{t('libre_download.debited', { count: choix.debitees })}</p>}
          <p>
            {choix.continuable
              ? t('libre_download.not_in_file', { count: choix.libres })
              : t('libre_download.none_paid')}
          </p>
        </div>
        <div className="tl-fenetre__actions">
          {choix.continuable && (
            <Button variant="secondary" onClick={onContinuer}>{t('libre_download.continue')}</Button>
          )}
          <Button onClick={onAcheter}>
            {t('libre_download.buy', { count: choix.libres })}
          </Button>
        </div>
      </div>
    </>,
    document.body,
  );
}
