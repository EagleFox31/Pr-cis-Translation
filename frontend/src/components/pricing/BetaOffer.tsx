import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import type { BetaProgram } from '../../hooks/useBetaProgram';

/**
 * Bandeau Bêta des tarifs, à gauche de l'achat à la page et de même structure
 * (titre, phrase, quatre repères, bouton). Affiché seulement si les
 * candidatures sont ouvertes (cf. `PricingCards`).
 */
export default function BetaOffer({ program }: { program: BetaProgram }) {
  const { t, i18n } = useTranslation();
  const n = (value: number) => value.toLocaleString(i18n.language);
  const quotas = [
    ['PDF', n(program.limits.pdf) + ' ' + t('beta.units.pages')],
    ['PowerPoint', n(program.limits.pptx) + ' ' + t('pricing.beta_slides')],
    ['Word', n(program.limits.docx) + ' ' + t('beta.units.words')],
    ['Excel', n(program.limits.xlsx) + ' ' + t('beta.units.sheets')],
  ];
  return (
    <aside className="pricing-strip pricing-strip--beta" aria-label={t('beta.title')}>
      <div>
        <p className="pricing-strip__title"><span className="pricing-strip__dot" aria-hidden="true" />
          {t('pricing.beta_title', { days: program.access_days })}</p>
        <p className="pricing-strip__text">{t('pricing.beta_lead', { count: program.capacity })}</p>
      </div>
      <Link className="beta-primary pricing-strip__btn" to="/beta">{t('pricing.beta_apply')} →</Link>
      <ul className="pricing-strip__chips" aria-label={t('beta.default_limits')}>
        {quotas.map(([format, value]) => <li key={format}>{format} <b>{value}</b></li>)}
      </ul>
    </aside>
  );
}
