import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Check, CreditCard, Download, HelpCircle, Monitor, ShieldCheck } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { usePricing, formatMoney } from '../hooks/usePricing';
import { goToSection } from '../lib/sectionBus';

import IntegrationsNav from '../components/IntegrationsNav';
import { useExtensionInstalled } from '../hooks/useExtensionInstalled';
import {
  detecterNavigateurPrecis, estMobile, EXTENSION_URL, EXTENSION_ZIP, versionPlusAncienne,
} from '../lib/extension';
import '../components/admin/admin.css';
import '../legal.css';
import '../extension-page.css';

type Boutique = 'edge' | 'chrome';

// Navigateurs pris en charge (même extension) ; Edge passe par sa boutique, les autres par le Chrome Web Store.
const NAVIGATEURS = [
  { id: 'chrome', nom: 'Google Chrome' },
  { id: 'edge', nom: 'Microsoft Edge' },
  { id: 'brave', nom: 'Brave' },
  { id: 'opera', nom: 'Opera' },
  { id: 'vivaldi', nom: 'Vivaldi' },
] as const;
type NavId = (typeof NAVIGATEURS)[number]['id'];
type Copie = 'idle' | 'ok' | 'erreur';

const FAQ = ['browsers', 'account', 'data', 'uninstall'] as const;
const PERMISSIONS = ['storage', 'tab', 'sites', 'send', 'sale'] as const;

// Rubriques du menu latéral : l'ancre de l'adresse ouvre directement la bonne.
const RUBRIQUES = [
  { id: 'install', cle: 'extension_page.tab_install', Icone: Download },
  { id: 'price', cle: 'extension_page.price.title', Icone: CreditCard },
  { id: 'perms', cle: 'extension_page.permissions.title', Icone: ShieldCheck },
  { id: 'faq', cle: 'extension_page.faq.title', Icone: HelpCircle },
] as const;
const DOCUMENTS = [
  ['/conditions', 'footer.terms'],
  ['/confidentialite', 'footer.privacy'],
  ['/mentions-legales', 'footer.legal'],
  ['/cookies', 'footer.cookies'],
] as const;
const NOM_BOUTIQUE = { edge: 'Edge Add-ons', chrome: 'Chrome Web Store' } as const;

// Installation directe (sans boutique) : adresse de la page des extensions, libellés propres
// au navigateur et captures réelles (Chrome et Edge) rangées dans /public/guides.
const GUIDES: Record<NavId, { adresse: string; dev: 'chrome' | 'edge'; charger: 'chrome' | 'edge' | 'opera'; captures: Partial<Record<number, string[]>> }> = {
  chrome: { adresse: 'chrome://extensions', dev: 'chrome', charger: 'chrome', captures: { 3: ['chrome-1-mode-developpeur'], 4: ['chrome-2-charger'] } },
  edge: { adresse: 'edge://extensions', dev: 'edge', charger: 'edge', captures: { 3: ['edge-1-mode-developpeur'], 4: ['edge-2-charger', 'edge-3-installee'] } },
  brave: { adresse: 'brave://extensions', dev: 'chrome', charger: 'chrome', captures: {} },
  opera: { adresse: 'opera://extensions', dev: 'chrome', charger: 'opera', captures: {} },
  vivaldi: { adresse: 'vivaldi://extensions', dev: 'chrome', charger: 'chrome', captures: {} },
};
type Rubrique = (typeof RUBRIQUES)[number]['id'];

const rubriqueInitiale = (): Rubrique => {
  const h = window.location.hash.slice(1);
  return RUBRIQUES.some((r) => r.id === h) ? (h as Rubrique) : 'install';
};

export default function ExtensionPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { pricing } = usePricing();

  // « Voir les tarifs » : l'accueil ne lit pas le #hash au chargement ; on y va,
  // puis on attend que la section existe pour la faire défiler.
  const voirTarifs = () => {
    navigate('/home');
    const debut = Date.now();
    const viser = () => {
      if (document.getElementById('pricing')) goToSection('pricing');
      else if (Date.now() - debut < 8000) window.setTimeout(viser, 150);
    };
    window.setTimeout(viser, 150);
  };
  const [params] = useSearchParams();
  const scrollRef = useRef<HTMLDivElement>(null);
  const corpsRef = useRef<HTMLDivElement>(null);
  const [copie, setCopie] = useState<Copie>('idle');
  const [copieAdresse, setCopieAdresse] = useState<Copie>('idle');

  const precis = detecterNavigateurPrecis();
  const [choix, setChoix] = useState<NavId>(precis === 'autre' ? 'chrome' : precis);
  const [rubrique, setRubrique] = useState<Rubrique>(rubriqueInitiale);

  const mobile = estMobile();
  const { installe, version } = useExtensionInstalled();
  const bienvenue = params.get('bienvenue') === '1';

  // Guide du navigateur choisi : sa boutique (Edge Add-ons ou Chrome Web Store).
  const nomChoix = NAVIGATEURS.find((n) => n.id === choix)!.nom;
  const boutique: Boutique = choix === 'edge' ? 'edge' : 'chrome';
  const urlBoutique = EXTENSION_URL[boutique];
  const miseAJour = !urlBoutique && installe && !!version && !!EXTENSION_ZIP.version
    && versionPlusAncienne(version, EXTENSION_ZIP.version);

  useEffect(() => {
    document.title = t('extension_page.doc_title');
    scrollRef.current?.scrollTo(0, 0);
  }, [t, i18n.language]);

  const choisirRubrique = (r: Rubrique) => {
    setRubrique(r);
    window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}#${r}`);
    // La page garde sa position ; seul le corps de la fiche revient en haut.
    corpsRef.current?.scrollTo(0, 0);
  };

  const choisirNavigateur = (id: NavId) => {
    setChoix(id);
    setCopieAdresse('idle');
  };

  const copierAdresse = async (adresse: string) => {
    try {
      await navigator.clipboard.writeText(adresse);
      setCopieAdresse('ok');
    } catch {
      setCopieAdresse('erreur');
    }
  };

  const copierLien = async () => {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/extension`);
      setCopie('ok');
    } catch {
      setCopie('erreur');
    }
  };

  const telecharger = (libelle: string) => (
    <a className="ext-btn ext-btn--primary" href={EXTENSION_ZIP.url} download="precis-extension.zip">
      <Download size={16} strokeWidth={2.2} aria-hidden="true" />
      {libelle}
    </a>
  );

  // État en tête de l'installation : mobile (copier le lien) ou extension déjà présente.
  const statut = () => {
    if (mobile) {
      return (
        <div className="ext-cta">
          <p className="ext-cta__note"><Monitor size={16} aria-hidden="true" /> {t('extension_page.mobile_title')}</p>
          <p className="ext-cta__hint">{t('extension_page.mobile_hint')}</p>
          <button type="button" className="ext-btn ext-btn--primary" onClick={copierLien}>
            {t('extension_page.copy_link')}
          </button>
          <span className="ext-cta__status" role="status">
            {copie === 'ok' && t('extension_page.copied')}
            {copie === 'erreur' && t('extension_page.copy_error')}
          </span>
        </div>
      );
    }
    if (installe) {
      return (
        <div className="ext-cta">
          <p className="ext-installed" role="status">
            <Check size={18} strokeWidth={2.4} aria-hidden="true" />
            {version ? t('extension_page.installed', { version }) : t('extension_page.installed_nov')}
          </p>
          {miseAJour && (
            <>
              <p className="ext-cta__hint">{t('extension_page.update_available', { version: EXTENSION_ZIP.version })}</p>
              <div className="ext-cta__row">{telecharger(t('extension_page.update_cta'))}</div>
            </>
          )}
        </div>
      );
    }
    return null;
  };

  const etape = (num: number, titre: string, texte: string, suite?: ReactNode) => (
    <li key={num}>
      <span className="ext-steps__num" aria-hidden="true">{num}</span>
      <div>
        <strong>{titre}</strong>
        <p>{texte}</p>
        {suite}
      </div>
    </li>
  );

  const guide = GUIDES[choix];
  const captures = (num: number) => guide.captures[num]?.map((nom) => (
    <figure key={nom} className="ext-shot">
      <img
        src={`/guides/${nom}.webp`} width={1280} height={720} loading="lazy"
        alt={t('extension_page.manual.shot_alt', { step: t(`extension_page.manual.s${num}_title`), browser: nomChoix })}
      />
    </figure>
  ));

  // Boutique publiée : les trois étapes en un clic ; sinon le guide du navigateur choisi.
  const etapes = urlBoutique
    ? (['add', 'pin', 'use'] as const).map((k, i) =>
      etape(i + 1, t(`extension_page.how.${k}_title`), t(`extension_page.how.${k}_text`)))
    : [
      etape(1, t('extension_page.manual.s1_title'), t('extension_page.manual.s1_text')),
      etape(2, t('extension_page.manual.s2_title'), t('extension_page.manual.s2_text', { browser: nomChoix }), (
        <div className="ext-address">
          <code>{guide.adresse}</code>
          <button type="button" className="ext-btn ext-btn--ghost ext-btn--small" onClick={() => copierAdresse(guide.adresse)}>
            {t('extension_page.manual.copy')}
          </button>
          <span className="ext-cta__status" role="status">
            {copieAdresse === 'ok' && t('extension_page.manual.copied')}
            {copieAdresse === 'erreur' && t('extension_page.copy_error')}
          </span>
        </div>
      )),
      etape(3, t('extension_page.manual.s3_title'), t(`extension_page.manual.s3_text_${guide.dev}`), captures(3)),
      etape(4, t('extension_page.manual.s4_title'), t(`extension_page.manual.s4_text_${guide.charger}`), captures(4)),
      etape(5, t('extension_page.manual.s5_title'), t('extension_page.manual.s5_text')),
    ];


  // En-tête fixe, pleine largeur : accroche, statut et choix du navigateur.
  const entete = (
    <>
      <section className="ext-hero">
        <p className="ext-hero__lead">{t('extension_page.lead')}</p>
        {statut()}
      </section>

      {!mobile && (
          <div className="ext-browsers ext-pick">
            <p className="ext-browsers__title" id="ext-pick">{t('extension_page.cards_title')}</p>
            <div className="ext-browsers__grid" role="radiogroup" aria-labelledby="ext-pick">
              {NAVIGATEURS.map((n) => (
                <button
                  key={n.id} type="button" role="radio" aria-checked={choix === n.id}
                  className={`ext-browser${choix === n.id ? ' ext-browser--current' : ''}`}
                  onClick={() => choisirNavigateur(n.id)}
                >
                  {n.id === precis && <span className="ext-browser__badge">{t('extension_page.card_detected')}</span>}
                  <img className="ext-browser__logo" src={`/browsers/${n.id}.png`} alt="" width={48} height={48} />
                  <span className="ext-browser__name">{n.nom}</span>
                </button>
              ))}
            </div>
            <p className="ext-cta__hint">{t('extension_page.card_unsupported')}</p>
          </div>
      )}
    </>
  );

  const bouton = urlBoutique ? (
    <a className="ext-btn ext-btn--primary" href={urlBoutique} target="_blank" rel="noopener">
      <Download size={16} strokeWidth={2.2} aria-hidden="true" />
      {t('extension_page.download_for', { browser: nomChoix })}
    </a>
  ) : telecharger(t('extension_page.download_for', { browser: nomChoix }));

  // Fiche de droite, sur le modèle de la fiche utilisateur de l'administration.
  const fiche = (titre: string, corps: ReactNode, action?: ReactNode, sous?: string, pied?: ReactNode) => (
    <section className="admin-panel ext-panel" aria-labelledby="ext-panel-title">
      <header className="admin-panel__head">
        <div>
          <h2 id="ext-panel-title">{titre}</h2>
          {sous && <p className="admin-panel__muted ext-panel__sub" title={sous}>{sous}</p>}
        </div>
        {action && <div className="admin-panel__head-actions">{action}</div>}
      </header>
      <div className="admin-panel__body" ref={corpsRef}>{corps}</div>
      {pied && <footer className="ext-panel__foot">{pied}</footer>}
    </section>
  );

  const fait = (cle: string, valeur: ReactNode) => (
    <div><dt>{t(`extension_page.${cle}`)}</dt><dd>{valeur}</dd></div>
  );

  const contenu = () => {
    switch (rubrique) {
      case 'price':
        return fiche(t('extension_page.price.title'), (
          <>
            <p className="ext-lead">{t('extension_page.price.text')}</p>
            <section className="admin-panel__block ext-section">
              <div className="admin-panel__block-head"><h3>{t('extension_page.price.count_title')}</h3></div>
              <dl className="admin-panel__facts ext-tiles">
                {fait('price.fact_text', t('extension_page.price.fact_text_v'))}
                {fait('price.fact_image', t('extension_page.price.fact_image_v'))}
                {fait('price.fact_video', t('extension_page.price.fact_video_v'))}
                {fait('price.fact_fail', t('extension_page.price.fact_fail_v'))}
              </dl>
            </section>
            <section className="admin-panel__block ext-section">
              <div className="admin-panel__block-head"><h3>{t('extension_page.price.plans_title')}</h3></div>
              {pricing ? (
                <ul className="ext-plans">
                  {pricing.plans.map((p) => (
                    <li key={p.key}>
                      <strong>{p.label}</strong>
                      <span>{p.monthly_pages === null
                        ? t('extension_page.price.pages_unlimited')
                        : t('extension_page.price.pages_month', { count: p.monthly_pages })}</span>
                      <span className="ext-plans__price">{p.monthly === null
                        ? t('extension_page.price.quote')
                        : p.monthly === 0 ? t('extension_page.price.free')
                        : `${formatMoney(p.monthly, pricing.currency, pricing.decimals, i18n.language)}${t('extension_page.price.per_month')}`}</span>
                    </li>
                  ))}
                  <li>
                    <strong>{t('extension_page.price.payg')}</strong>
                    <span>{t('extension_page.price.payg_hint')}</span>
                    <span className="ext-plans__price">{formatMoney(pricing.page_price, pricing.currency, pricing.decimals, i18n.language)}{t('extension_page.price.per_page')}</span>
                  </li>
                </ul>
              ) : null}
            </section>
            <section className="admin-panel__block ext-section">
              <div className="admin-panel__block-head"><h3>{t('extension_page.price.know_title')}</h3></div>
              <ul className="ext-checks">
                {(['know_credits', 'know_order', 'know_carry', 'know_limits'] as const).map((k) => (
                  <li key={k}><Check size={16} strokeWidth={2.4} aria-hidden="true" />{t(`extension_page.price.${k}`)}</li>
                ))}
              </ul>
            </section>
          </>
        ), (
          <button type="button" className="ext-btn ext-btn--primary" onClick={voirTarifs}>
            {t('extension_page.price.link')}
          </button>
        ), undefined, (
          <nav className="ext-docs" aria-label={t('extension_page.price.docs_title')}>
            <span>{t('extension_page.price.docs_title')}</span>
            {DOCUMENTS.map(([to, cle]) => <Link key={to} className="ext-link" to={to}>{t(cle)}</Link>)}
          </nav>
        ));
      case 'perms':
        return fiche(t('extension_page.permissions.title'), (
          <section className="admin-panel__block ext-section">
            <ul className="ext-list">
              {PERMISSIONS.map((k) => <li key={k}>{t(`extension_page.permissions.${k}`)}</li>)}
            </ul>
            <p><Link className="ext-link" to="/confidentialite">{t('extension_page.permissions.privacy')}</Link></p>
          </section>
        ));
      case 'faq':
        return fiche(t('extension_page.faq.title'), (
          <section className="admin-panel__block ext-section">
            {FAQ.map((k) => (
              <details key={k} className="ext-faq">
                <summary>{t(`extension_page.faq.${k}_q`)}</summary>
                <p>{t(`extension_page.faq.${k}_a`)}</p>
              </details>
            ))}
          </section>
        ));
      default:
        if (mobile) return null;
        return fiche(t('extension_page.install_for', { browser: nomChoix }), (
          <>
            <section className="admin-panel__block">
              <dl className="admin-panel__facts">
                {fait('fact_browser', (
                  <span className="ext-fact-browser">
                    <img src={`/browsers/${choix}.png`} alt="" width={20} height={20} />{nomChoix}
                  </span>
                ))}
                {fait('fact_store', urlBoutique ? NOM_BOUTIQUE[boutique] : t('extension_page.manual.fact_store_v'))}
                {fait('fact_install', t(urlBoutique ? 'extension_page.fact_install_v' : 'extension_page.manual.fact_install_v'))}
                {fait('fact_updates', t(urlBoutique ? 'extension_page.fact_updates_v' : 'extension_page.manual.fact_updates_v'))}
              </dl>
            </section>
            <section className="admin-panel__block ext-section" aria-labelledby="ext-steps-title">
              <div className="admin-panel__block-head"><h3 id="ext-steps-title">{t('extension_page.steps_title')}</h3></div>
              <ol className="ext-steps">{etapes}</ol>
            </section>
            {!urlBoutique && (
              <section className="admin-panel__block ext-section">
                <div className="admin-panel__block-head"><h3>{t('extension_page.manual.notes_title')}</h3></div>
                <ul className="ext-list">
                  {(['note_folder', 'note_update', 'note_alert'] as const).map((k) => (
                    <li key={k}>{t(`extension_page.manual.${k}`)}</li>
                  ))}
                </ul>
              </section>
            )}
          </>
        ), bouton, urlBoutique
          ? t('extension_page.card_one_click')
          : t('extension_page.manual.sub', { version: EXTENSION_ZIP.version }));
    }
  };

  return (
    <div className="legal-page ext-page">
      <IntegrationsNav />

      <main className="legal-main">
        <div className="legal-head">
          <div className="legal-head__inner">
            <h1>{t('extension_page.title')}</h1>
          </div>
        </div>

        <div className="legal-scroll" ref={scrollRef}>
          <div className="legal-body ext-body">
            {bienvenue && (
              <section className="ext-welcome" aria-labelledby="ext-welcome-title">
                <h2 id="ext-welcome-title">{t('extension_page.welcome.title')}</h2>
                <ol>
                  <li>{t('extension_page.welcome.pin')}</li>
                  <li>{t('extension_page.welcome.login')}</li>
                  <li>{t('extension_page.welcome.try')}</li>
                </ol>
              </section>
            )}

            {entete}

            <div className="ext-layout">
              <nav className="admin-list ext-menu" aria-label={t('extension_page.menu_title')}>
                {RUBRIQUES.map(({ id, cle, Icone }) => (
                  <button
                    key={id} type="button" className="admin-row admin-row--button admin-duo__row ext-menu__row"
                    aria-current={rubrique === id ? 'true' : undefined}
                    onClick={() => choisirRubrique(id)}
                  >
                    <span className="ext-menu__icon"><Icone size={18} strokeWidth={2} aria-hidden="true" /></span>
                    <span className="admin-row__main">
                      <span className="admin-row__title">{t(cle)}</span>
                      <span className="admin-row__meta">{t(`extension_page.menu_hint_${id}`)}</span>
                    </span>
                  </button>
                ))}
              </nav>

              <div className="ext-content">{contenu()}</div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
