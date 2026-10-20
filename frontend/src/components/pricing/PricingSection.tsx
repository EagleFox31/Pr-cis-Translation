import { useTranslation } from 'react-i18next';
import PlanToggle from './PlanToggle';
import PricingCards from './PricingCards';

interface PricingSectionProps {
  isAnnual: boolean;
  onAnnualChange: (annual: boolean) => void;
}

export default function PricingSection({ isAnnual, onAnnualChange }: PricingSectionProps) {
  const { t } = useTranslation();

  return (
    <section className="pricing-section" id="pricing">
      <div className="section-inner">
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '20px',
            marginBottom: '40px',
          }}
        >
          <div>
            <span className="section-tag">{t('pricing.tag')}</span>
            <h2
              className="section-title"
              style={{ marginBottom: 0 }}
              dangerouslySetInnerHTML={{ __html: t('pricing.title') }}
            />
          </div>
          <PlanToggle isAnnual={isAnnual} onChange={onAnnualChange} />
        </div>

        <PricingCards isAnnual={isAnnual} />
      </div>
    </section>
  );
}
