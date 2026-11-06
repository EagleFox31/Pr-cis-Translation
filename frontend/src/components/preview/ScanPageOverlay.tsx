import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2, ScanText } from 'lucide-react';
import type { ChoixPage } from '../../hooks/useDocumentLibrary';
import type { PagesIllisiblesVue } from '../../hooks/usePagesIllisibles';

interface Props {
  /** Page affichée. */
  page: number;
  scanPages: PagesIllisiblesVue;
}

const BOUTON_SECONDAIRE = {
  padding: '8px 12px', borderRadius: '6px',
  border: '1px solid #94a3b8', background: 'transparent',
  color: 'var(--gray-700)', fontSize: '12.5px', fontWeight: 600,
  fontFamily: 'inherit', cursor: 'pointer',
} as const;

/** Décision sur la page traduite elle-même, quand le scan n'a pas pu être lu
 *  ou que la page a été laissée hors de la sélection.
 *  Sans choix : une carte OPAQUE cache le côté traduit (l'original ne doit
 *  jamais y transparaître). Avec un choix : une petite étiquette « Modifier ».
 *  Rien si la page est lisible ou a été traduite après coup. */
export default function ScanPageOverlay({ page, scanPages }: Props) {
  const { t } = useTranslation();
  const { pages, enCours, choisir, erreur, occupe, provisoire } = scanPages;
  // Pages dont l'utilisateur a rouvert la décision.
  const [modif, setModif] = useState<number[]>([]);
  const [toutes, setToutes] = useState(false);
  const [erreurPour, setErreurPour] = useState<number | null>(null);

  const info = pages.find((p) => p.page === page);
  if (!info) return null;

  // Page laissée hors de la sélection : mêmes gestes, sauf « Retirer » au
  // lieu de « Laisser vide ».
  const horsSel = info.motif === 'hors_selection';
  const enLecture = enCours.includes(page);
  const carte = enLecture || info.choix === null || modif.includes(page);

  if (!carte) {
    return (
      <div
        style={{
          position: 'absolute', top: '8px', right: '8px', zIndex: 25,
          display: 'inline-flex', alignItems: 'center', gap: '6px',
          padding: '3px 10px', borderRadius: '999px',
          background: 'rgba(255,255,255,0.94)', border: '1px solid #fde68a',
          boxShadow: '0 1px 4px rgba(15,23,42,0.12)',
          fontSize: '11.5px', color: 'var(--gray-600)',
        }}
      >
        <span>{t(`viewer.scan.tag_${info.choix}`)}</span>
        <span aria-hidden>·</span>
        <button
          type="button"
          onClick={() => setModif((m) => [...m, page])}
          style={{
            padding: 0, border: 'none', background: 'none', font: 'inherit',
            fontWeight: 600, color: 'var(--blue)', textDecoration: 'underline', cursor: 'pointer',
          }}
        >
          {t('viewer.scan.tag_edit')}
        </button>
      </div>
    );
  }

  // Pages que « Appliquer à toutes » vise : celles de même nature, pas déjà en lecture.
  const candidates = pages
    .filter((p) => (p.motif === 'hors_selection') === horsSel && !enCours.includes(p.page))
    .map((p) => p.page);
  const plusieurs = candidates.length > 1;
  const cible = toutes && plusieurs ? candidates : [page];

  const decider = async (choix: ChoixPage) => {
    const ok = await choisir(cible, choix);
    if (ok) {
      setModif((m) => m.filter((n) => !cible.includes(n)));
      setToutes(false);
      setErreurPour(null);
    } else {
      setErreurPour(page);
    }
  };

  return (
    <div
      role="group"
      aria-label={t(horsSel ? 'viewer.scan.hs_title' : 'viewer.scan.card_title', { page })}
      style={{
        position: 'absolute', inset: 0, zIndex: 25,
        // La page elle-même : texte et boutons posés à même le papier.
        background: '#fffefb', padding: '7%', overflowY: 'auto',
        display: 'flex',
      }}
    >
      <div
        style={{
          margin: 'auto', width: '100%', maxWidth: '340px',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px',
          color: 'var(--gray-600)',
        }}
      >
      <ScanText size={26} strokeWidth={1.8} style={{ color: '#a8a29e', flexShrink: 0 }} aria-hidden />
      <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--gray-800)',
                     textAlign: 'center', textWrap: 'balance' }}>
        {t(horsSel ? 'viewer.scan.hs_title' : 'viewer.scan.card_title', { page })}
      </span>
      <span style={{ fontSize: '12.5px', lineHeight: 1.55, color: 'var(--gray-600)', marginTop: '-4px',
                     textAlign: 'justify', textAlignLast: 'center', hyphens: 'auto' }}>
        {t(horsSel ? 'viewer.scan.hs_hint'
           : info.motif === 'solde' ? 'viewer.scan.motif_solde' : 'viewer.scan.hint')}
      </span>

      {provisoire ? (
        <span role="status" style={{ fontSize: '12.5px', fontWeight: 600, color: 'var(--gray-700)', textAlign: 'center', textWrap: 'balance' }}>
          {t('viewer.scan.card_wait')}
        </span>
      ) : enLecture ? (
        <span
          role="status"
          style={{
            display: 'inline-flex', alignItems: 'center', gap: '8px',
            fontSize: '13px', fontWeight: 600, color: 'var(--gray-700)',
          }}
        >
          <Loader2 size={16} className="scanp-spin" style={{ color: '#2563eb' }} aria-hidden />
          {t('viewer.scan.card_reading')}
        </span>
      ) : (
        <>
          {plusieurs && (
            <label
              style={{
                display: 'inline-flex', alignItems: 'center', gap: '8px',
                fontSize: '12.5px', color: 'var(--gray-700)', cursor: 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={toutes}
                disabled={occupe}
                onChange={(e) => setToutes(e.target.checked)}
              />
              {t(horsSel ? 'viewer.scan.apply_all_hs' : 'viewer.scan.apply_all',
                 { count: candidates.length })}
            </label>
          )}
          <button
            type="button"
            disabled={occupe}
            onClick={() => decider('traduire')}
            style={{
              width: '100%', marginTop: '4px', padding: '9px 18px', borderRadius: '6px',
              border: '1.5px solid var(--blue)', background: 'transparent',
              color: 'var(--blue)', fontSize: '13px', fontWeight: 600,
              fontFamily: 'inherit', cursor: occupe ? 'default' : 'pointer',
              opacity: occupe ? 0.6 : 1,
            }}
          >
            {t(horsSel ? 'viewer.scan.do_traduire_hs' : 'viewer.scan.do_traduire',
               { count: cible.length })}
          </button>
          <div style={{ width: '100%', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            {(horsSel ? ['original', 'retirer'] as const : ['original', 'vide'] as const).map((c) => (
              <button
                key={c}
                type="button"
                disabled={occupe}
                onClick={() => decider(c)}
                style={{ ...BOUTON_SECONDAIRE, opacity: occupe ? 0.6 : 1,
                         cursor: occupe ? 'default' : 'pointer' }}
              >
                {t(`viewer.scan.do_${c}`)}
              </button>
            ))}
          </div>
        </>
      )}

      {erreur && erreurPour === page && (
        <span role="alert" style={{ fontSize: '12.5px', color: '#b91c1c', textAlign: 'center', textWrap: 'balance' }}>
          {erreur}
        </span>
      )}
      </div>
    </div>
  );
}
