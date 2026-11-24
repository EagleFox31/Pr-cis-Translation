import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronDown, ChevronUp, ImageIcon } from 'lucide-react';
import type { DocImage } from '../../hooks/useDocumentLibrary';

interface Props {
  docId: string;
  load: (id: string) => Promise<DocImage[]>;
  setOriginal: (id: string, cle: string, originale: boolean) => Promise<boolean>;
  /** Appelé après un changement réussi : l'aperçu doit être recalculé. */
  onChanged: () => void;
}

/** Images traduites d'un document de la bibliothèque : pour chacune, l'avant /
 *  après et un bouton pour remettre l'original (ou rétablir la traduction).
 *  Rien n'apparaît si le document n'a aucune image traduite. */
export default function DocumentImagesPanel({ docId, load, setOriginal, onChanged }: Props) {
  const { t } = useTranslation();
  const [images, setImages] = useState<DocImage[]>([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let alive = true;
    setImages([]);
    setOpen(false);
    setError(false);
    load(docId).then((l) => { if (alive) setImages(l); }).catch(() => {});
    return () => { alive = false; };
  }, [docId, load]);

  if (images.length === 0) return null;

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
