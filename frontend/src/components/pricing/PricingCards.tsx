import { useTranslation } from 'react-i18next';
import { motion } from 'motion/react';
import { useAuth } from '../../contexts/AuthContext';
import { usePricing, formatMoney, type PricingPlan } from '../../hooks/usePricing';
import Skeleton from '../ui/Skeleton';

interface PricingCardsProps {
  isAnnual: boolean;
}

function formatBytes(bytes: number): string {
  if (bytes >= 1_073_741_824) return `${Math.round(bytes / 1_073_741_824)} Go`;
  if (bytes >= 1_048_576) return `${Math.round(bytes / 1_048_576)} Mo`;
  return `${Math.round(bytes / 1024)} Ko`;
}

/** Ce que chaque offre promet, en trois lignes maximum.
 *
 *  La règle tenue ici : une carte se COMPARE d'un coup d'œil. L'ancienne
 *  version mélangeait un quota de mots (« 10 000 mots / mois ») et un quota de
 *  pages selon les cartes — deux unités qu'on ne peut pas comparer de tête. On
 *  parle donc de PAGES partout, parce que c'est ce que l'utilisateur dépose.
 */
function features(plan: PricingPlan, p: { currency: string; decimals: number; page_price: number },
                 locale: string): { text: string; off?: boolean }[] {
  const pages = plan.monthly_pages;
  const storage = plan.storage > 0 ? `${formatBytes(plan.storage)} de stockage` : null;

  if (plan.key === 'free') {
    return [
      { text: '1 page traduite offerte chaque mois' },
      // LE point de l'offre gratuite, et la raison pour laquelle elle a sa
      // place à côté d'abonnements : au-delà de la page offerte, on paie
      // l'unité, sans s'engager. Le prix est annoncé ici, pas découvert au
      // moment de payer.
      { text: `Puis ${formatMoney(p.page_price, p.currency, p.decimals, locale)} par page — payées avant traduction` },
      { text: 'Aucun abonnement, aucune carte à enregistrer' },
      { text: 'Aucun stockage — vos documents ne sont pas conservés', off: true },
    ];
  }

  if (plan.key === 'enterprise') {
    return [
      { text: 'Volume illimité, engagement annuel' },
      { text: 'Accès API et facturation automatique' },
      { text: 'Support dédié et SLA garanti' },
      { text: `${formatBytes(plan.storage)} de stockage` },
    ];
  }

  const base = [
    { text: pages === null ? 'Pages illimitées' : `${pages} pages par mois` },
    { text: 'Téléchargement des traductions inclus' },
    { text: plan.key === 'pro' ? 'Support prioritaire' : 'Support standard' },
  ];
  if (storage) base.push({ text: storage });
  return base;
}

export default function PricingCards({ isAnnual }: PricingCardsProps) {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const { pricing, loading } = usePricing();

  if (loading) {
    return (
      <div className="pricing-grid">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="pricing-card">
            <Skeleton height={260} />
          </div>
        ))}
      </div>
    );
  }

  // Le serveur n'a pas répondu. On le dit, plutôt que d'afficher des prix de
  // secours qui pourraient ne plus être ceux pratiqués.
  if (!pricing) {
    return (
      <p style={{ textAlign: 'center', color: 'var(--gray-500)', fontSize: '14px' }}>
        Les tarifs sont momentanément indisponibles. Réessayez dans un instant.
      </p>
    );
  }

  const locale = i18n.language || 'fr';

  return (
    <div className="pricing-grid">
      {pricing.plans.map((plan, idx) => {
        const isActive = user ? user.plan === plan.key : false;
        const isPopular = plan.key === 'pro';
        const amount = isAnnual ? plan.annual : plan.monthly;
        const onQuote = amount === null;

        return (
          <motion.div
            key={plan.key}
            className={`pricing-card ${isPopular ? 'popular' : ''} ${isActive ? 'active' : ''}`}
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.1 }}
            transition={{ duration: 0.5, delay: idx * 0.1, ease: [0.16, 1, 0.3, 1] }}
            whileHover={isPopular
              ? { y: -8, boxShadow: '0 24px 60px rgba(13,27,62,0.18)' }
              : { y: -4, boxShadow: '0 16px 40px rgba(13,27,62,0.12)' }}
            style={isActive
              ? { border: '2px solid var(--blue)', boxShadow: '0 0 0 4px rgba(26,77,199,0.12)' }
              : undefined}
          >
            {isPopular && <div className="popular-badge">{t('pricing.recommended')}</div>}

            <div className="pricing-plan">{plan.label}</div>

            <div className="pricing-price">
              {onQuote ? (
                <span className="period">Sur devis</span>
              ) : amount === 0 ? (
                <>0<span className="period">/mois</span></>
              ) : (
                <>
                  {formatMoney(amount, pricing.currency, pricing.decimals, locale)}
                  <span className="period">/mois</span>
                </>
              )}
            </div>

            {/* L'engagement annuel se facture à l'année : le dire ici évite de
                laisser croire qu'on peut résilier au mois à ce prix-là. */}
            {isAnnual && !onQuote && amount !== 0 && (
              <p style={{ fontSize: '12px', color: 'var(--blue)', margin: '0 0 8px', fontWeight: 600 }}>
                facturé annuellement
              </p>
            )}

            <div className="pricing-divider" />

            <ul className="pricing-features">
              {features(plan, pricing, locale).map((f, i) => (
                <li key={i} className={f.off ? 'unavailable' : ''}>{f.text}</li>
              ))}
            </ul>

            <a
              href={!user && plan.key === 'free' ? '/login' : '#'}
              className="btn-pricing"
              onClick={(e) => { if (!(!user && plan.key === 'free')) e.preventDefault(); }}
              style={isActive
                ? { background: 'var(--gray-200)', borderColor: 'var(--gray-300)', color: 'var(--gray-500)', cursor: 'default', pointerEvents: 'none' }
                : undefined}
            >
              {isActive ? 'Forfait actif'
                : plan.key === 'free' ? 'Commencer gratuitement'
                : onQuote ? 'Nous contacter'
                : `Choisir ${plan.label}`}
            </a>
          </motion.div>
        );
      })}
    </div>
  );
}
