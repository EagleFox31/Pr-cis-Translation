/**
 * La grille des offres.
 *
 * CE QUI A CHANGÉ
 * ---------------
 * Le CONTENU des cartes était écrit en français dans le code — « Volume
 * illimité », « Aucun abonnement », « Sur devis », « Forfait actif ». Neuf
 * chaînes que l'interface anglaise affichait en français. Elles vivent
 * maintenant dans les dictionnaires ; le composant ne fait plus que choisir la
 * bonne clé selon l'offre.
 *
 * Et un TROISIÈME `formatBytes` maison écrivait « Go / Mo / Ko » en dur — le
 * même que la barre latérale et le compte avaient déjà chacun le leur. Il est
 * remplacé par `lib/format.formatSize`, dont les unités suivent la langue.
 *
 * CE QUI N'A PAS CHANGÉ
 * ---------------------
 * On parle de PAGES partout, jamais de mots. Une carte se compare d'un coup
 * d'œil : mélanger « 10 000 mots » et « 50 pages » selon les offres, c'était
 * deux unités qu'on ne peut pas rapporter l'une à l'autre de tête.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import { motion } from 'motion/react';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '../../contexts/AuthContext';
import { usePricing, formatMoney, type PricingPlan } from '../../hooks/usePricing';
import { formatSize } from '../../lib/format';
import Skeleton from '../ui/Skeleton';
import BetaOffer from './BetaOffer';
import PaymentModal from '../payment/PaymentModal';
import { openSupport } from '../support/supportBus';
import type { PlanChoice } from '../../hooks/usePayment';

interface PricingCardsProps {
  isAnnual: boolean;
}

interface Feature {
  text: string;
  /** Barré : présent dans l'offre pour la comparaison, mais pas fourni. */
  off?: boolean;
}

/** Les lignes d'une carte, dans la langue de l'interface. */
function features(
  plan: PricingPlan,
  t: TFunction,
): Feature[] {
  const stockage = (): Feature => ({
    text: t('pricing.feat_storage', { size: formatSize(plan.storage, t) }),
  });

  // La VITESSE est le levier de vente principal : le gratuit passe en file
  // standard, chaque palier payant remonte dans la file. On la nomme sur
  // chaque carte pour que « payer = aller plus vite » se lise d'un coup d'œil.
  const vitesse = (): Feature => {
    const key = plan.priority >= 3 ? 'pricing.feat_speed_dedicated'
      : plan.priority === 2 ? 'pricing.feat_speed_max'
      : plan.priority === 1 ? 'pricing.feat_speed_priority'
      : 'pricing.feat_speed_standard';
    // La file standard n'est pas un manque : c'est l'offre gratuite. On ne la
    // barre donc pas — mais elle contraste avec le « prioritaire » d'à côté.
    return { text: t(key) };
  };

  if (plan.key === 'free') {
    return [
      { text: t('pricing.feat_free_page', { count: plan.monthly_pages ?? 0 }) },
      { text: t('pricing.feat_all_formats') },
      { text: t('pricing.feat_download') },
      vitesse(),
      { text: t('pricing.feat_free_no_storage'), off: true },
    ];
  }

  if (plan.key === 'enterprise') {
    return [
      { text: t('pricing.feat_ent_unlimited') },
      vitesse(),
      { text: t('pricing.feat_ent_api') },
      { text: t('pricing.feat_ent_support') },
      stockage(),
    ];
  }

  const base: Feature[] = [
    { text: plan.monthly_pages === null
        ? t('pricing.feat_pages_unlimited')
        : t('pricing.feat_pages_monthly', { count: plan.monthly_pages }) },
    vitesse(),
    { text: t('pricing.feat_download') },
    { text: plan.key === 'pro'
        ? t('pricing.feat_support_priority')
        : t('pricing.feat_support_standard') },
  ];
  if (plan.storage > 0) base.push(stockage());
  return base;
}

export default function PricingCards({ isAnnual }: PricingCardsProps) {
  const { t, i18n } = useTranslation();
  const { user, refreshUser } = useAuth();
  const { pricing, loading } = usePricing();
  // Navigation interne : un lien plein rechargerait l'application (et son écran d'accueil).
  const navigate = useNavigate();
  const [buying, setBuying] = useState<PlanChoice | null>(null);
  // Séparé du plan : la modale garde son contenu pendant l'animation de fermeture.
  const [payOpen, setPayOpen] = useState(false);
  // Achat de pages à l'unité, sans forfait.
  const [packOpen, setPackOpen] = useState(false);
  const [packPages, setPackPages] = useState(2);

  if (loading) {
    return (
      <div className="pricing-grid pricing-grid--with-beta">
        <BetaOffer />
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
    return <div className="pricing-grid pricing-grid--with-beta">
      <BetaOffer />
      <p className="pricing-indispo">{t('pricing.unavailable')}</p>
    </div>;
  }

  const locale = i18n.language || 'fr';
  // Rang dans la grille d'achat, fourni par le serveur (qui refuse de même
  // d'acheter moins que ce qu'on a). Hors grille (entreprise, admin) : tout
  // ce qui s'achète en ligne est déjà inclus.
  const rankOf = (key: string) => pricing.plans.find((p) => p.key === key)?.rank ?? null;
  const userRank = user ? (rankOf(user.plan) ?? Infinity) : -1;
  // Abonnement acheté : il a une fin, à renouveler avant (Campay ne prélève pas).
  const until = user?.plan_expires_at
    ? new Date(user.plan_expires_at).toLocaleDateString(locale, { dateStyle: 'long' })
    : null;

  return (
    <>
    <div className="pricing-grid pricing-grid--with-beta">
      <BetaOffer />
      {pricing.plans.map((plan, idx) => {
        const isActive = user ? user.plan === plan.key : false;
        const isPopular = plan.key === 'pro';
        const billedTotal = isAnnual ? plan.annual_total : plan.monthly_total;
        const amount = billedTotal === null ? null : billedTotal / (isAnnual ? 12 : 1);
        const onQuote = amount === null;
        const forSale = plan.for_sale && !onQuote;
        const renew = isActive && forSale && until !== null;
        const included = !!user && plan.rank !== null && !isActive && userRank > plan.rank;
        // Visiteur : tout bouton mène à la connexion, sauf l'offre gratuite
        // déjà active pour personne. Connecté : le bouton agit sur place.
        const toLogin = !user && (plan.key === 'free' || forSale || onQuote);
        const act = () => {
          if (onQuote) openSupport({ category: 'subscription' });
          else if (forSale && (renew || (!isActive && !included))) {
            setBuying({ key: plan.key, label: plan.label, annual: isAnnual });
            setPayOpen(true);
          }
        };

        return (
          <motion.div
            key={plan.key}
            className={[
              'pricing-card',
              isPopular ? 'popular' : '',
              isActive ? 'active' : '',
            ].filter(Boolean).join(' ')}
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.1 }}
            transition={{ duration: 0.5, delay: idx * 0.1, ease: [0.16, 1, 0.3, 1] }}
            whileHover={isPopular
              ? { y: -8, boxShadow: '0 24px 60px rgba(13,27,62,0.18)' }
              : { y: -4, boxShadow: '0 16px 40px rgba(13,27,62,0.12)' }}
          >
            {isPopular && <div className="popular-badge">{t('pricing.recommended')}</div>}

            <div className="pricing-plan">{plan.label}</div>

            <div className="pricing-price">
              {onQuote ? (
                <span className="period">{t('pricing.on_quote')}</span>
              ) : amount === 0 ? (
                <>0<span className="period">{t('pricing.per_month')}</span></>
              ) : (
                <>
                  {isAnnual && billedTotal !== null && billedTotal % 12 !== 0 ? '≈ ' : ''}
                  {formatMoney(amount, pricing.currency, pricing.decimals, locale)}
                  <span className="period">{t('pricing.per_month')}</span>
                </>
              )}
            </div>

            {/* L'engagement annuel se facture à l'année : le dire ici évite de
                laisser croire qu'on peut résilier au mois à ce prix-là. */}
            {isAnnual && billedTotal !== null && billedTotal !== 0 && (
              <p className="pricing-annuel">{t('pricing.billed_annually_total', {
                total: formatMoney(billedTotal, pricing.currency, pricing.decimals, locale),
              })}</p>
            )}

            <div className="pricing-divider" />

            <ul className="pricing-features">
              {features(plan, t).map((f, i) => (
                <li key={i} className={f.off ? 'unavailable' : ''}>{f.text}</li>
              ))}
            </ul>

            <a
              href={toLogin ? '/login' : '#'}
              className={`btn-pricing${isActive && !renew ? ' btn-pricing--actif' : ''}`}
              aria-disabled={included || (isActive && !renew) || undefined}
              onClick={(e) => { e.preventDefault(); if (toLogin) navigate('/login'); else act(); }}
            >
              {renew ? t('pricing.renew')
                : isActive ? t('pricing.active_plan')
                : included ? t('pricing.included')
                : plan.key === 'free' ? t('pricing.start_free')
                : onQuote ? t('pricing.contact_us')
                : t('pricing.choose', { plan: plan.label })}
            </a>
            {isActive && until && (
              <p className="pricing-annuel">{t('pricing.active_until', { date: until })}</p>
            )}
          </motion.div>
        );
      })}
    </div>

    <p className="pricing-annuel">{t('pricing.fees_included')}</p>
    <p className="pricing-annuel">{t('pricing.equivalence', { count: pricing.words_per_page })}</p>

    {/* Payer à la page, sans s'abonner : une offre à part entière, sous la
        grille, et non un lien accroché à la seule carte Gratuit. Les pages
        achetées restent créditées sur le compte jusqu'à leur utilisation. */}
    <div className="pricing-payg">
      <div>
        <p className="pricing-payg__title">{t('pricing.payg_title')}</p>
        <p className="pricing-payg__text">
          {t('pricing.payg_text', {
            price: formatMoney(pricing.page_price, pricing.currency, pricing.decimals, locale) })}
        </p>
        <p className="pricing-annuel">{t('pricing.payg_fees', { percent: pricing.fee_percent })}</p>
      </div>
      <a href={user ? '#' : '/login'} className="btn-pricing pricing-payg__btn"
         onClick={(e) => { e.preventDefault(); if (user) setPackOpen(true); else navigate('/login'); }}>
        {t('pricing.buy_pages')}
      </a>
    </div>

    <PaymentModal
      open={payOpen && buying !== null}
      onClose={() => setPayOpen(false)}
      pages={0}
      plan={buying ?? undefined}
      label={buying ? t('payment.plan_label', { plan: buying.label }) : ''}
      onPaid={() => { void refreshUser(); }}
    />

    <PaymentModal
      open={packOpen}
      onClose={() => setPackOpen(false)}
      pages={packPages}
      onPagesChange={setPackPages}
      label={t('payment.buy_credits_label')}
      onPaid={() => { void refreshUser(); }}
    />
    </>
  );
}
