import { useTranslation } from 'react-i18next';
import { motion } from 'motion/react';

const criteria = [
  'visual', 'meaning', 'boxes', 'style', 'ocr', 'data',
];

export default function ComparisonTable() {
  const { t } = useTranslation();

  return (
    <section className="comparison-section" id="comparison">
      <div className="section-inner">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: [0.4, 0, 0.2, 1] }}
          viewport={{ once: true, amount: 0.1 }}
        >
          <div className="comp-section-label">{t('comparison.label')}</div>
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
                      <td>{t(`comparison.row_${c}`)}</td>
                      <td className="td-precis">
                        <div className="comp-val">
                          <span className="comp-chk yes">✓</span>
                          <span className="comp-text yes">{t(`comparison.row_${c}_precis`)}</span>
                        </div>
                      </td>
                      <td className="td-other">
                        <div className="comp-val">
                          <span className="comp-chk no">–</span>
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
                  <div className="comp-mobile-criterion">{t(`comparison.row_${c}`)}</div>
                  <div className="comp-mobile-cols">
                    <div className="comp-mobile-col p">
                      <div className="comp-mobile-col-name p">{t('comparison.header_precis')}</div>
                      <div className="comp-mobile-col-val p">{t(`comparison.row_${c}_precis`)}</div>
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
        </motion.div>
      </div>
    </section>
  );
}
