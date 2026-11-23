/**
 * « Traduire à nouveau » : relance un document terminé depuis son original
 * gardé sur le serveur, vers la langue choisie. L'ancien document reste dans
 * « Mes documents » ; le prix est celui d'un nouveau dépôt.
 */
import { useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { X } from 'lucide-react';
import type { DocMeta } from '../../hooks/useDocumentLibrary';
import LanguagePicker from '../upload/LanguagePicker';
import Button from '../ui/Button';
import '../nouveautes/modal.css';

export default function FenetreRetraduire({ doc, onConfirm, onClose }: {
  doc: DocMeta;
  onConfirm: (targetLang: string) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const uid = useId();
  const boite = useRef<HTMLDivElement>(null);
  const [langue, setLangue] = useState(doc.targetLang);

  useEffect(() => {
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
        <button type="button" className="nvd__x" onClick={onClose} aria-label={t('retranslate.close')}>
          <X size={18} aria-hidden="true" />
        </button>
        <div className="nvd__head">
          <h2 id={`${uid}-t`}>{t('retranslate.title')}</h2>
        </div>
        <div id={`${uid}-d`} className="tl-fenetre__texte">
          <p>{t('retranslate.text', { name: doc.originalName })}</p>
          <p>{t('retranslate.price')}</p>
        </div>
        <div style={{ marginTop: '14px' }}>
          <LanguagePicker value={langue} onChange={setLangue} ext={doc.ext} />
          {langue === doc.targetLang && (
            <p role="status" style={{ marginTop: '7px', fontSize: '13px', color: 'var(--gray-600)' }}>
              {t('retranslate.same_target')}
            </p>
          )}
        </div>
        <div className="tl-fenetre__actions">
          <Button variant="secondary" onClick={onClose}>{t('retranslate.cancel')}</Button>
          <Button onClick={() => onConfirm(langue)}>{t('retranslate.confirm')}</Button>
        </div>
      </div>
    </>,
    document.body,
  );
}
