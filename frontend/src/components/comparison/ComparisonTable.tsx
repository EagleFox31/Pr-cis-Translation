import { useTranslation } from 'react-i18next';
import {
  Palette, BrainCircuit, Box, SlidersHorizontal, Image as ImageIcon, ShieldCheck,
  Check, Minus,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

export const criteriaIcons: Record<string, LucideIcon> = {
  visual: Palette,
  meaning: BrainCircuit,
  boxes: Box,
  style: SlidersHorizontal,
  ocr: ImageIcon,
  data: ShieldCheck,
};

/** Rend l'icône Lucide d'un critère (taille homogène dans le tableau). */
function CriterionIcon({ name }: { name: string }) {
  const Icon = criteriaIcons[name];
  if (!Icon) return null;
  return <Icon size={16} strokeWidth={1.9} />;
}

const criteria = [
  'visual', 'meaning', 'boxes', 'style', 'ocr', 'data',
];

/** Contenu brut du comparatif (sans enveloppe <section>) — utilisé dans FeaturesGrid */
export default function ComparisonContent() {
  const { t } = useTranslation();

  return (
    <>
      <div className="comp-section-label" style={{ marginTop: '48px' }}>{t('comparison.label')}</div>
      <div className="comp-box">
            <div className="comp-box-header">
              <h3>{t('comparison.title')}</h3>
              <div className="comp-header-badges">
                <span className="comp-hbadge precis">{t('comparison.header_precis')}</span>
                <span className="comp-vs">VS</span>
                <span className="comp-hbadge other">{t('comparison.header_other')}</span>
              </div>
            </div>

            {/* Desktop table */}
            <div className="comp-table-wrap">
              <table className="comp-table">
                <thead>
                  <tr>
                    <th style={{ width: '34%' }}>{t('comparison.col_criterion')}</th>
                    <th className="th-precis" style={{ width: '33%' }}>{t('comparison.header_precis')}</th>
                    <th className="th-other" style={{ width: '33%' }}>{t('comparison.header_other')}</th>
                  </tr>
                </thead>
                <tbody>
                  {criteria.map((c) => (
                    <tr key={c}>
                      <td>
                        <span className="comp-criterion-name">
                          <span className="comp-criterion-icon"><CriterionIcon name={c} /></span>
                          {t(`comparison.row_${c}`)}
                        </span>
                      </td>
                      <td className="td-precis">
                        <div className="comp-val">
                          {c === 'ocr' ? (
                            <span className="comp-badge-pill">{t(`comparison.row_${c}_precis`)}</span>
                          ) : (
                            <>
                              <span className="comp-chk yes"><Check size={13} strokeWidth={3} /></span>
                              <span className="comp-text yes">{t(`comparison.row_${c}_precis`)}</span>
                            </>
                          )}
                        </div>
                      </td>
                      <td className="td-other">
                        <div className="comp-val">
                          <span className="comp-chk no"><Minus size={13} strokeWidth={3} /></span>
                          <span className="comp-text no">{t(`comparison.row_${c}_other`)}</span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <div className="comp-mobile-cards">
              {criteria.map((c) => (
                <div key={c} className="comp-mobile-item">
                  <div className="comp-mobile-criterion">
                    <span className="comp-criterion-icon"><CriterionIcon name={c} /></span>
                    {t(`comparison.row_${c}`)}
                  </div>
                  <div className="comp-mobile-cols">
                    <div className="comp-mobile-col p">
                      <div className="comp-mobile-col-name p">{t('comparison.header_precis')}</div>
                      <div className="comp-mobile-col-val p">
                        {c === 'ocr' ? (
                          <span className="comp-badge-pill">{t(`comparison.row_${c}_precis`)}</span>
                        ) : (
                          t(`comparison.row_${c}_precis`)
                        )}
                      </div>
                    </div>
                    <div className="comp-mobile-col o">
                      <div className="comp-mobile-col-name o">{t('comparison.header_other')}</div>
                      <div className="comp-mobile-col-val o">{t(`comparison.row_${c}_other`)}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
      </div>
    </>
  );
}
