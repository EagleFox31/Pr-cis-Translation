import { useTranslation } from 'react-i18next';
import { motion } from 'motion/react';

interface PricingCardsProps {
  isAnnual: boolean;
}

const plans = [
  { index: 1, key: 'freemium', popular: false },
  { index: 2, key: 'starter', popular: false },
  { index: 3, key: 'pro', popular: true },
  { index: 4, key: 'enterprise', popular: false },
];

export default function PricingCards({ isAnnual }: PricingCardsProps) {
  const { t } = useTranslation();

  return (
    <div className="pricing-grid">
      {plans.map((plan, idx) => (
        <motion.div
          key={plan.key}
          className={`pricing-card ${plan.popular ? 'popular' : ''}`}
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.1 }}
          transition={{ duration: 0.5, delay: idx * 0.1, ease: [0.16, 1, 0.3, 1] }}
          whileHover={plan.popular ? { y: -8, boxShadow: '0 24px 60px rgba(13,27,62,0.18)' } : { y: -4, boxShadow: '0 16px 40px rgba(13,27,62,0.12)' }}
        >
          {plan.popular && <div className="popular-badge">{t('pricing.recommended')}</div>}

          <div className="pricing-plan">{t(`pricing.plan_${plan.index}_name`)}</div>

          <div className="pricing-price">
            {plan.key === 'freemium'
              ? t('pricing.plan_1_price')
              : plan.key === 'enterprise'
                ? t('pricing.plan_4_price')
                : isAnnual
                  ? t(`pricing.plan_${plan.index}_price_annual`)
                  : t(`pricing.plan_${plan.index}_price_monthly`)}
            {plan.key !== 'enterprise' && (
              <>
                <sup>€</sup>
                <span className="period">{t(`pricing.plan_${plan.index}_period`)}</span>
              </>
            )}
            {plan.key === 'enterprise' && (
              <span className="period">{t('pricing.plan_4_period')}</span>
            )}
          </div>

          <p className="pricing-desc">{t(`pricing.plan_${plan.index}_desc`)}</p>
          <div className="pricing-divider" />

          <ul className="pricing-features">
            {plan.key === 'freemium' && (
              <>
                <li>{t('pricing.plan_1_words')}</li>
                <li>{t('pricing.feat_preview_only')}</li>
                <li>{t('pricing.feat_no_download')}</li>
              </>
            )}
            {plan.key === 'starter' && (
              <>
                <li>{t('pricing.plan_2_words')}</li>
                <li>{t('pricing.feat_download_included')}</li>
                <li>{t('pricing.feat_support_standard')}</li>
                {isAnnual && (
                  <li style={{ color: 'var(--blue)', fontWeight: 'bold' }}>
                    {t('pricing.feat_discount_included')}
                  </li>
                )}
              </>
            )}
            {plan.key === 'pro' && (
              <>
                <li>{t('pricing.plan_3_words')}</li>
                <li>{t('pricing.feat_support_priority')}</li>
                <li>{t('pricing.feat_trial_text')}</li>
                {isAnnual && (
                  <li style={{ color: 'var(--blue)', fontWeight: 'bold' }}>
                    {t('pricing.feat_save_text')}
                  </li>
                )}
              </>
            )}
            {plan.key === 'enterprise' && (
              <>
                <li>{t('pricing.plan_4_words')}</li>
                <li>{t('pricing.feat_api_access')}</li>
                <li>{t('pricing.feat_sla_guaranteed')}</li>
                <li>{t('pricing.feat_excess_rate')}</li>
              </>
            )}
          </ul>

          <a
            href="#"
            className="btn-pricing"
            onClick={(e) => e.preventDefault()}
          >
            {plan.key === 'freemium'
              ? t('pricing.btn_start')
              : plan.key === 'pro'
                ? t('pricing.btn_choose_pro')
                : t('pricing.btn_choose')}
          </a>
        </motion.div>
      ))}
    </div>
  );
}
