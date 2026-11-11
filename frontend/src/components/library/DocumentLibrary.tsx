/**
 * Panneau « Mon compte » : l'identité et le solde, les nouveautés, la liste des
 * documents (recherche, menus par ligne), puis le pied (inviter, aide, sortie).
 *
 * Le comportement est celui d'avant — mêmes requêtes, mêmes droits, même
 * modale de paiement ; seule la mise en page suit la maquette
 * `panneau-compte.html`. Ce fichier ne garde que son rôle : ouvrir, lister,
 * orchestrer.
 *   • le haut (identité, solde) -> `AccountPanel`
 *   • une ligne                 -> `DocumentCard` (+ `RowMenu`)
 *   • le tiroir                 -> `ui/Drawer` (Échap, focus, défilement gelé)
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Files, Info, LifeBuoy, LogOut, Search, Trash2, UserPlus, X } from 'lucide-react';

import type { DocMeta } from '../../hooks/useDocumentLibrary';
import type { StopMode } from '../../hooks/useStreamingTranslation';
import { useAuth } from '../../contexts/AuthContext';
import { isTrialFor } from '../../lib/plans';
import Alert from '../ui/Alert';
import Button from '../ui/Button';
import Drawer from '../ui/Drawer';
import EmptyState from '../ui/EmptyState';
import Skeleton from '../ui/Skeleton';
import PaymentModal from '../payment/LazyPaymentModal';
import { openSupport } from '../support/supportBus';
import { openInvite } from '../invite/inviteBus';
import AccountPanel from './AccountPanel';
import DocumentCard from './DocumentCard';
import NouveautesLigne from './NouveautesLigne';
import RowMenu from './RowMenu';

interface DocumentLibraryProps {
  isOpen: boolean;
  onClose: () => void;
  documents: DocMeta[];
  /** L'aperçu s'ouvre AVANT que les fichiers soient là : on remonte des
   *  promesses, pas des blobs. Attendre le rendu avant d'ouvrir, c'était offrir
   *  une fenêtre figée pendant plusieurs secondes.
   *
   *  La TRADUCTION n'est pas remontée ici : elle se demande page par page, et
   *  `Home` en est le seul propriétaire. Deux endroits qui la chargent, c'est
   *  deux requêtes pour la même page et une course pour savoir laquelle gagne. */
  onPreview: (req: {
    docId: string;
    filename: string;
    ext: string;
    paid: boolean;
    /** Traduction encore en cours côté serveur. */
    enCours: boolean;
    source: Promise<Blob | undefined>;
  }) => void;
  onDelete: (id: string) => void;
  onClearAll: () => void;
  getBlob: (id: string) => Promise<Blob | undefined>;
  getOriginalBlob: (id: string, asPdf?: boolean) => Promise<Blob | undefined>;
  /** Un paiement vient d'aboutir : la liste doit être relue (le `paid` du
   *  document a changé côté serveur). */
  onPaid?: () => void;
  /** Relance la traduction d'un document en erreur. */
  onRetry?: (doc: DocMeta) => void;
  /** Pause / Annuler une traduction en cours. */
  onStop?: (doc: DocMeta, mode: StopMode) => Promise<void>;
  /** La liste est en cours de lecture (premier chargement). */
  loading?: boolean;
  /** La lecture de la liste a échoué. */
  erreur?: boolean;
  /** Relit la liste (bouton « Réessayer »). */
  onRefresh?: () => void;
}

export default function DocumentLibrary({
  isOpen, onClose, documents, onPreview, onDelete, onClearAll,
  getBlob, getOriginalBlob, onPaid, onRetry, onStop,
  loading: enChargement = false, erreur: enErreur = false, onRefresh,
}: DocumentLibraryProps) {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  // Le serveur refuse le téléchargement d'une traduction à un plan d'essai
  // (402). On lit le MÊME plan côté client pour ne pas promettre un bouton qui
  // ne peut pas tenir.
  const trial = isTrialFor(user);

  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [requete, setRequete] = useState('');
  // Document dont on est en train de régler les pages (null = pas de paiement).
  const [payFor, setPayFor] = useState<DocMeta | null>(null);

  // À la fermeture du tiroir, la recherche repart de zéro : rouvert, il ne doit
  // pas montrer une liste filtrée par une requête oubliée. (La confirmation de
  // « Tout effacer » vit dans le menu, qui disparaît avec le tiroir.)
  useEffect(() => {
    if (!isOpen) setRequete('');
  }, [isOpen]);

  // On n'ATTEND rien ici. L'aperçu rastérisé se calcule côté serveur en
  // quelques secondes ; le retenir jusqu'au bout laissait l'utilisateur devant
  // une interface morte, sans même un indicateur. On lance la requête et on
  // passe la main tout de suite.
  //
  // `as=pdf` : le viewer affiche tout en PDF et le serveur détient déjà cette
  // conversion. Lui renvoyer le natif pour qu'il la refasse était un
  // aller-retour de plusieurs mégaoctets par ouverture.
  const handlePreview = useCallback((doc: DocMeta) => {
    onPreview({
      docId: doc.id, paid: doc.paid,
      filename: doc.filename,
      ext: doc.ext,
      enCours: doc.status === 'translating',
      source: getOriginalBlob(doc.id, true),
    });
  }, [getOriginalBlob, onPreview]);

  const handleDownload = useCallback(async (doc: DocMeta) => {
    // Un compte gratuit dont le document est payé télécharge ; sinon on lui
    // propose de le régler — sur place, pour ce document précis. L'ancienne
    // version le renvoyait vers la grille de tarifs : la seule issue offerte
    // était de s'abonner, alors qu'il ne voulait qu'un fichier.
    if (trial && !doc.paid) {
      setPayFor(doc);
      return;
    }
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
  }, [getBlob, trial]);

  const versForfaits = () => {
    onClose();
    navigate('/home#pricing');
  };

  const q = requete.trim().toLowerCase();
  const visibles = useMemo(
    () => (q
      ? documents.filter(d => `${d.originalName} ${d.filename}`.toLowerCase().includes(q))
      : documents),
    [documents, q]);
  // Un visiteur n'a rien à charger ; une relecture ratée ne cache pas une liste déjà là.
  const loading = enChargement && !!user;
  const erreur = enErreur && !!user && documents.length === 0;
  const avecArchives = documents.some(d => d.archive);
  const listeVisible = !loading && !erreur && documents.length > 0;

  return (
    <>
      <Drawer open={isOpen} onClose={onClose} label={t('library.title')}
        width="min(420px, 100vw)">
        <div className="panneau">
          {user && <AccountPanel user={user}
            refreshKey={documents.map(d => `${d.id}:${d.status}`).join('|')}
            onClose={onClose} />}
          {user && <NouveautesLigne user={user} onClose={onClose} />}

          <section className="docs" aria-labelledby="docs-t">
            <div className="docs-head">
              <h2 id="docs-t" tabIndex={-1}>{t('library.title')}</h2>
              {listeVisible && <span className="n tab">{documents.length}</span>}
              {listeVisible && (
                <RowMenu label={t('library.list_options')}
                  entries={[{
                    key: 'clear', label: t('library.clear_all'), danger: true,
                    icon: <Trash2 size={16} strokeWidth={2} className="ic" aria-hidden="true" />,
                    onSelect: onClearAll,
                    // La liste entière disparaît : le focus va au titre de la section.
                    apres: 'ligne',
                    confirmation: {
                      question: t('library.clear_confirm_question'),
                      confirmLabel: t('library.confirm_clear'),
                      cancelLabel: t('library.cancel'),
                    },
                  }]} />
              )}
              {!user && (
                <button type="button" className="iconbtn" aria-label={t('library.close')} onClick={onClose}>
                  <X size={20} strokeWidth={2} aria-hidden="true" />
                </button>
              )}
            </div>

            {listeVisible && (
              <div className="find">
                <Search size={16} strokeWidth={2} className="ic" aria-hidden="true" />
                <input type="search" value={requete}
                  placeholder={t('library.search_placeholder')}
                  aria-label={t('library.search_aria')}
                  onChange={e => setRequete(e.target.value)}
                  onKeyDown={e => {
                    // Échap vide la recherche avant de fermer le panneau.
                    if (e.key === 'Escape' && requete) {
                      e.stopPropagation();
                      setRequete('');
                    }
                  }} />
              </div>
            )}

            {listeVisible && avecArchives && (
              <p className="archive-note">
                <Info size={14} strokeWidth={2} aria-hidden="true" />
                <span>
                  {t('library.archive_note')}{' '}
                  <a href="/home#pricing" onClick={e => { e.preventDefault(); versForfaits(); }}>
                    {t('library.archive_note_link')}
                  </a>
                </span>
              </p>
            )}

            {loading ? (
              <div className="list list--loading" aria-busy="true">
                {[0, 1, 2].map(i => <Skeleton key={i} height="60px" borderRadius="var(--radius)" />)}
              </div>
            ) : erreur ? (
              <div className="list-state">
                <Alert tone="error">{t('library.load_error')}</Alert>
                {onRefresh && (
                  <Button variant="ghost" size="sm" onClick={onRefresh}>{t('library.retry')}</Button>
                )}
              </div>
            ) : documents.length === 0 ? (
              <EmptyState
                icon={<Files size={44} strokeWidth={1.4} />}
                title={user ? t('library.empty_title') : undefined}
                message={user ? t('library.empty_message') : t('library.empty_guest')}
                action={user ? (
                  <small className="mono">{t('library.empty_formats')}</small>
                ) : (
                  <Button variant="primary" size="md"
                    onClick={() => { onClose(); navigate('/login'); }}>
                    {t('nav.signIn')}
                  </Button>
                )}
              />
            ) : visibles.length === 0 ? (
              <p className="nomatch">{t('library.no_match')}</p>
            ) : (
              <ul className="list">
                {visibles.map((doc) => (
                  <DocumentCard
                    key={doc.id}
                    doc={doc}
                    trial={trial}
                    busy={loadingId === doc.id}
                    onPreview={handlePreview}
                    onDownload={handleDownload}
                    onDelete={onDelete}
                    onRetry={onRetry}
                    onStop={onStop}
                  />
                ))}
              </ul>
            )}
          </section>

          <footer className={user ? 'p-foot' : 'p-foot p-foot--solo'}>
            {user && (
              <button type="button" onClick={() => { onClose(); openInvite(); }}>
                <UserPlus size={18} strokeWidth={2} aria-hidden="true" />
                {t('invite.open')}
              </button>
            )}
            <button type="button" onClick={() => { onClose(); openSupport(); }}>
              <LifeBuoy size={18} strokeWidth={2} aria-hidden="true" />
              {t('support.open')}
            </button>
            {user && (
              <button type="button" onClick={async () => { onClose(); await logout(); }}>
                <LogOut size={18} strokeWidth={2} aria-hidden="true" />
                {t('account.logout')}
              </button>
            )}
          </footer>
        </div>
      </Drawer>

      <PaymentModal
        open={!!payFor}
        onClose={() => setPayFor(null)}
        pages={payFor?.pageCount ?? 1}
        documentId={payFor?.id}
        label={t('library.unlock_label', { name: payFor?.originalName ?? '' })}
        onPaid={() => { onPaid?.(); setPayFor(null); }}
      />
    </>
  );
}
