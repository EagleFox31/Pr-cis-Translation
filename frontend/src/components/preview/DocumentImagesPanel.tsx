import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronDown, ChevronUp, ImageIcon, Loader2 } from 'lucide-react';
import type { DocImage, PropositionImages } from '../../hooks/useDocumentLibrary';

type Acceptation = { ok: true; images: DocImage[] } | { ok: false; credits: number | null };

interface Props {
  docId: string;
  load: (id: string) => Promise<DocImage[]>;
  setOriginal: (id: string, cle: string, originale: boolean) => Promise<boolean>;
  /** Proposition de traduire les images à texte, lues pendant la traduction. */
  loadProposition: (id: string) => Promise<PropositionImages>;
  translate: (id: string) => Promise<Acceptation>;
  /** Solde insuffisant : ouvre l'achat de crédits pour `pages` pages. */
  onBuyPages: (pages: number) => void;
  /** Appelé après un changement réussi : l'aperçu doit être recalculé. */
  onChanged: () => void;
}

const SONDAGE_MS = 5000;

/** Images d'un document de la bibliothèque.
 *  - Avant décision : « N images sur M contiennent du texte à traduire » et le
 *    bouton « Traduire (N pages) » (achat de crédits si le solde manque).
 *  - Après : pour chaque image traduite, l'avant / après et un bouton pour
 *    remettre l'original (ou rétablir la traduction).
 *  Rien n'apparaît si le document n'a aucune image à texte. */
export default function DocumentImagesPanel({ docId, load, setOriginal, loadProposition, translate,
                                              onBuyPages, onChanged }: Props) {
  const { t } = useTranslation();
  const [images, setImages] = useState<DocImage[]>([]);
  const [prop, setProp] = useState<PropositionImages | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let alive = true;
    setImages([]);
    setProp(null);
    setOpen(false);
    setError(false);
    load(docId).then((l) => { if (alive) setImages(l); }).catch(() => {});
    return () => { alive = false; };
  }, [docId, load]);

  // Proposition : relue tant que la lecture des images n'est pas finie.
  useEffect(() => {
    let alive = true;
    let minuterie: ReturnType<typeof setTimeout> | undefined;
    const lire = () => {
      loadProposition(docId).then((p) => {
        if (!alive) return;
        setProp(p);
        if (p.etat === 'en_cours') minuterie = setTimeout(lire, SONDAGE_MS);
      }).catch(() => {});
    };
    lire();
    return () => { alive = false; if (minuterie) clearTimeout(minuterie); };
  }, [docId, loadProposition]);

  const accepter = async () => {
    if (!prop) return;
    setBusy('*');
    setError(false);
    const res = await translate(docId).catch((): Acceptation => ({ ok: false, credits: null }));
    if ('images' in res) {
      setImages(res.images);
      setProp({ etat: 'faite', n: 0, total: 0 });
      onChanged();
    } else if (res.credits !== null) {
      onBuyPages(res.credits);
    } else {
      setError(true);
    }
    setBusy(null);
  };

  if (images.length === 0) {
    if (prop?.etat === 'en_cours') {
      return (
        <div className="docimg">
          <div className="docimg-bar" role="status">
            <Loader2 size={14} strokeWidth={2} className="ui-spin" aria-hidden />
            <span>{t('viewer.images.analysing')}</span>
          </div>
        </div>
      );
    }
    if (prop?.etat === 'pret' && prop.n > 0) {
      return (
        <div className="docimg">
          <div className="docimg-bar docimg-offer">
            <ImageIcon size={14} strokeWidth={2} aria-hidden />
            <span>{t('viewer.images.offer', { count: prop.total, n: prop.n })}</span>
            <span className="spacer" />
            <button type="button" className="tb-btn" disabled={busy !== null} onClick={accepter}>
              {busy ? <Loader2 size={14} className="ui-spin" aria-hidden /> : null}
              {t('viewer.images.offer_button', { count: prop.n })}
            </button>
          </div>
          {error && <p className="docimg-error" role="alert">{t('viewer.images.error')}</p>}
        </div>
      );
    }
    return null;
  }

  const basculer = async (img: DocImage) => {
    setBusy(img.cle);
    setError(false);
    const ok = await setOriginal(docId, img.cle, !img.originale).catch(() => false);
    if (ok) {
      setImages((prev) => prev.map((i) => (i.cle === img.cle ? { ...i, originale: !i.originale } : i)));
      onChanged();
    } else {
      setError(true);
    }
    setBusy(null);
  };

  const retirees = images.filter((i) => i.originale).length;

  return (
    <div className="docimg">
      <button type="button" className="docimg-bar" aria-expanded={open}
              onClick={() => setOpen((o) => !o)}>
        <ImageIcon size={14} strokeWidth={2} aria-hidden />
        <span>{t('viewer.images.title', { count: images.length })}</span>
        {retirees > 0 && (
          <span className="docimg-note">{t('viewer.images.restored', { count: retirees })}</span>
        )}
        <span className="spacer" />
        {open ? <ChevronUp size={14} aria-hidden /> : <ChevronDown size={14} aria-hidden />}
      </button>
      {open && error && <p className="docimg-error" role="alert">{t('viewer.images.error')}</p>}
      {open && (
        <div className="docimg-list">
          {images.map((img) => {
            const vue = img.originale ? img.vignette_originale : img.vignette_traduite;
            return (
              <div key={img.cle} className="docimg-card">
                <div className="docimg-thumb">
                  {vue ? <img src={vue} alt="" /> : <ImageIcon size={20} aria-hidden />}
                </div>
                <div className="docimg-meta">
                  <span className="docimg-state">
                    {img.originale ? t('viewer.images.state_original') : t('viewer.images.state_translated')}
                  </span>
                  {img.pages.length > 0 && (
                    <span className="docimg-pages">
                      {t('viewer.images.pages', { count: img.pages.length, pages: img.pages.join(', ') })}
                    </span>
                  )}
                  <button type="button" className="tb-btn ghost" disabled={busy !== null}
                          onClick={() => basculer(img)}>
                    {img.originale ? t('viewer.images.use_translation') : t('viewer.images.use_original')}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
