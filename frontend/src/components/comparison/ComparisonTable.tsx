import { useTranslation } from 'react-i18next';
import {
  FileOutput, BookOpen, Columns2, RotateCcw, Wallet, Check,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

/** Critères comparés, dans l'ordre d'affichage. */
const criteria: { key: string; Icon: LucideIcon }[] = [
  { key: 'output', Icon: FileOutput },
  { key: 'long', Icon: BookOpen },
  { key: 'preview', Icon: Columns2 },
  { key: 'resume', Icon: RotateCcw },
  { key: 'payment', Icon: Wallet },
];

/** Catégories d'outils comparées à Précis (aucune marque nommée). */
const others = ['ai', 'online'] as const;

/** Contenu brut du comparatif (sans enveloppe <section>) — utilisé dans FeaturesGrid */
export default function ComparisonContent() {
  const { t } = useTranslation();

  return (
    <div className="comp-box comp-box--3" style={{ marginTop: '32px' }}>
      <div className="comp-box-header">
        <h3>{t('comparison.title')}</h3>
      </div>

      {/* Bureau : un tableau, Précis en première colonne */}
      <div className="comp-table-wrap">
        <table className="comp-table">
          <thead>
            <tr>
              <th style={{ width: '22%' }}>{t('comparison.col_criterion')}</th>
              <th className="th-precis" style={{ width: '26%' }}>{t('comparison.col_precis')}</th>
              {others.map(o => (
                <th key={o} className="th-other" style={{ width: '26%' }}>{t(`comparison.col_${o}`)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {criteria.map(({ key, Icon }) => (
              <tr key={key}>
                <td>
                  <span className="comp-criterion-name">
                    <span className="comp-criterion-icon"><Icon size={16} strokeWidth={1.9} /></span>
                    {t(`comparison.row_${key}`)}
                  </span>
                </td>
                <td className="td-precis">
                  <div className="comp-val">
                    <span className="comp-chk yes"><Check size={13} strokeWidth={3} /></span>
                    <span className="comp-text yes">{t(`comparison.row_${key}_precis`)}</span>
                  </div>
                </td>
                {others.map(o => (
                  <td key={o} className="td-other">
                    <span className="comp-text no">{t(`comparison.row_${key}_${o}`)}</span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile : une carte par critère, les trois outils empilés */}
      <div className="comp-mobile-cards">
        {criteria.map(({ key, Icon }) => (
          <div key={key} className="comp-mobile-item">
            <div className="comp-mobile-criterion">
              <span className="comp-criterion-icon"><Icon size={16} strokeWidth={1.9} /></span>
              {t(`comparison.row_${key}`)}
            </div>
            <div className="comp-mobile-cols">
              <div className="comp-mobile-col p">
                <div className="comp-mobile-col-name p">{t('comparison.col_precis')}</div>
                <div className="comp-mobile-col-val p">{t(`comparison.row_${key}_precis`)}</div>
              </div>
              {others.map(o => (
                <div key={o} className="comp-mobile-col o">
                  <div className="comp-mobile-col-name o">{t(`comparison.col_${o}`)}</div>
                  <div className="comp-mobile-col-val o">{t(`comparison.row_${key}_${o}`)}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
