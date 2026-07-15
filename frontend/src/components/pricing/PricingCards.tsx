import { useTranslation } from 'react-i18next';
import { motion } from 'motion/react';
import { useAuth } from '../../contexts/AuthContext';


interface PricingCardsProps {
  isAnnual: boolean;
}

const PLANS = [
  { index: 1, planKey: 'free', storage: '0 Mo', storageBytes: 0, pages: '1 page' },
  { index: 2, planKey: 'starter', storage: '500 Mo', storageBytes: 524_288_000, pages: 'Illimité' },
  { index: 3, planKey: 'pro', storage: '2 Go', storageBytes: 2_147_483_648, pages: 'Illimité' },
  { index: 4, planKey: 'enterprise', storage: '10 Go', storageBytes: 10_737_418_240, pages: 'Illimité' },
];

function formatBytes(bytes: number): string {
  if (bytes >= 1_073_741_824) return `${(bytes / 1_073_741_824).toFixed(1)} Go`;
  if (bytes >= 1_048_576) return `${(bytes / 1_048_576).toFixed(0)} Mo`;
  return `${(bytes / 1024).toFixed(0)} Ko`;
}

export default function PricingCards({ isAnnual }: PricingCardsProps) {
  const { t } = useTranslation();
  const { user } = useAuth();

  return (
    <div className="pricing-grid">
      {PLANS.map((plan, idx) => {
        // Visiteur = aucun forfait actif ; Connecté = son plan
        const isActive = user ? user.plan === plan.planKey : false;
        const isPopular = plan.planKey === 'pro';

        return (
          <motion.div
            key={plan.planKey}
            className={`pricing-card ${isPopular ? 'popular' : ''} ${isActive ? 'active' : ''}`}
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.1 }}
            transition={{ duration: 0.5, delay: idx * 0.1, ease: [0.16, 1, 0.3, 1] }}
            whileHover={isPopular ? { y: -8, boxShadow: '0 24px 60px rgba(13,27,62,0.18)' } : { y: -4, boxShadow: '0 16px 40px rgba(13,27,62,0.12)' }}
            style={isActive ? { border: '2px solid var(--blue)', boxShadow: '0 0 0 4px rgba(26,77,199,0.12)' } : undefined}
          >
            {isPopular && <div className="popular-badge">{t('pricing.recommended')}</div>}

            <div className="pricing-plan">{t(`pricing.plan_${plan.index}_name`)}</div>

            <div className="pricing-price">
              {plan.planKey === 'free'
                ? t('pricing.plan_1_price')
                : plan.planKey === 'enterprise'
                  ? t('pricing.plan_4_price')
                  : isAnnual
                    ? t(`pricing.plan_${plan.index}_price_annual`)
                    : t(`pricing.plan_${plan.index}_price_monthly`)}
              {plan.planKey !== 'enterprise' && (
                <>
                  <sup>€</sup>
                  <span className="period">{t(`pricing.plan_${plan.index}_period`)}</span>
                </>
              )}
              {plan.planKey === 'enterprise' && (
                <span className="period">{t('pricing.plan_4_period')}</span>
              )}
            </div>

            <p className="pricing-desc">{t(`pricing.plan_${plan.index}_desc`)}</p>
            <div className="pricing-divider" />

            <ul className="pricing-features">
              {plan.planKey === 'free' && (
                <>
                  <li>{t('pricing.plan_1_words')}</li>
                  <li>{t('pricing.feat_preview_only')}</li>
                  <li className="unavailable">{t('pricing.feat_no_download')}</li>
                </>
              )}
              {plan.planKey === 'starter' && (
                <>
                  <li>{t('pricing.plan_2_words')}</li>
                  <li>{t('pricing.feat_download_included')}</li>
                  <li>{t('pricing.feat_support_standard')}</li>
                </>
              )}
              {plan.planKey === 'pro' && (
                <>
                  <li>{t('pricing.plan_3_words')}</li>
                  <li>{t('pricing.feat_support_priority')}</li>
                  <li>{t('pricing.feat_trial_text')}</li>
                </>
              )}
              {plan.planKey === 'enterprise' && (
                <>
                  <li>{t('pricing.plan_4_words')}</li>
                  <li>{t('pricing.feat_api_access')}</li>
                  <li>{t('pricing.feat_sla_guaranteed')}</li>
                  <li>{t('pricing.feat_excess_rate')}</li>
                </>
              )}

              {/* Stockage — en dernier, avant la réduction annuelle */}
              <li className={plan.planKey === 'free' ? 'unavailable' : ''}>
                {plan.planKey === 'free' ? 'Aucun stockage' : `${plan.storage} de stockage`}
              </li>

              {isAnnual && plan.planKey !== 'free' && plan.planKey !== 'enterprise' && (
                <li style={{ color: 'var(--blue)', fontWeight: 'bold' }}>
                  {plan.planKey === 'starter' ? t('pricing.feat_discount_included') : t('pricing.feat_save_text')}
                </li>
              )}
            </ul>

            <a
              href={!user && plan.planKey === 'free' ? '/login' : '#'}
              className="btn-pricing"
              onClick={(e) => { if (!(!user && plan.planKey === 'free')) e.preventDefault(); }}
              style={isActive ? { background: 'var(--gray-200)', borderColor: 'var(--gray-300)', color: 'var(--gray-500)', cursor: 'default', pointerEvents: 'none' } : undefined}>
              {!user && plan.planKey === 'free' ? 'Commencer' : isActive ? 'Forfait actif' : (
                plan.planKey === 'free' ? t('pricing.btn_start')
                : plan.planKey === 'pro' ? t('pricing.btn_choose_pro')
                : t('pricing.btn_choose')
              )}
            </a>
          </motion.div>
        );
      })}
    </div>
  );
}
