/**
 * Barre du haut, la même sur toutes les pages (accueil compris).
 *
 * POURQUOI : chaque famille de pages avait son menu ; on perdait ses repères en
 * changeant de page. Désormais le menu principal ne change jamais ; une rubrique
 * à plusieurs pages (Extension et API, Administration, Informations légales)
 * ajoute une 2ᵉ rangée sous la barre. Voir docs/etude-navigation-tarifs.md.
 *
 * Aucun chevauchement : la ligne se replie d'elle-même quand la place manque
 * (useRepli), la 2ᵉ rangée défile à l'horizontale, et la hauteur réelle de la
 * barre est publiée dans `--nav-total` pour décaler le contenu des pages.
 */
import type { MouseEvent, ReactNode } from 'react';
import { lazy, Suspense, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { ArrowUpRight, House } from 'lucide-react';
import { flushSync } from 'react-dom';

import { useAuth } from '../../contexts/AuthContext';
import MobileMenu from './MobileMenu';
import { useRepli } from './useRepli';
import '../admin/admin.css';
import './appbar.css';

// Tiroir « Mes documents » : chargé à la première ouverture seulement.
const BibliothequeHote = lazy(() => import('../library/BibliothequeHote'));

export interface AppBarLink {
  href: string;
  label: string;
  /** Pastille après le libellé (ex. « Bientôt »). */
  badge?: ReactNode;
}

interface AppBarProps {
  /** 2ᵉ rangée : pages de la rubrique en cours. */
  sub?: { label: string; links: AppBarLink[] };
  /** Accueil seulement : section visible et défilement vers une section. */
  section?: { active: string; onClick: (id: string) => void };
  /** Clic sur l'avatar ; par défaut ouvre « Mes documents ». */
  onAccount?: () => void;
}

interface Lien { id: string; label: string; href?: string }

/** Change de page avec un fondu court (View Transitions) ; immédiat si le
 *  navigateur ne le gère pas ou si l'utilisateur réduit les animations. */
function avecFondu(changer: () => void) {
  const doc = document as Document & { startViewTransition?: (f: () => void) => unknown };
  if (!doc.startViewTransition || window.matchMedia('(prefers-reduced-motion: reduce)').matches) changer();
  else doc.startViewTransition(() => flushSync(changer));
}

export default function AppBar({ sub, section, onAccount }: AppBarProps) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { user } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  // `null` : jamais ouvert (rien de monté) ; ensuite reste monté pour l'animation de fermeture.
  const [biblio, setBiblio] = useState<boolean | null>(null);
  const [scrolled, setScrolled] = useState(!section);
  const [progress, setProgress] = useState(0);
  const barre = useRef<HTMLElement>(null);
  const ligne = useRef<HTMLDivElement>(null);

  const fr = (i18n.language || 'fr').startsWith('fr');
  const admin = user?.plan === 'admin';
  const niveau = useRepli(ligne, `${i18n.language}|${user ? 1 : 0}|${admin ? 1 : 0}`);

  const liens: Lien[] = [
    { id: 'features', label: t('nav.features') },
    { id: 'story', label: t('nav.howItWorks') },
    { id: 'pricing', label: t('nav.pricing') },
    { id: 'about', label: t('nav.about') },
    // Puis les liens qui ouvrent une autre page (séparés et fléchés).
    { id: 'integrations', label: t('nav.integrations'), href: '/extension' },
    ...(admin ? [{ id: 'admin', label: t('admin.menu', 'Administration'), href: '/admin/users' }] : []),
  ];

  // Lien actif : la section visible sur l'accueil, la rubrique ailleurs.
  const actif = section
    ? (section.active === 'comparison' ? 'features' : section.active)
    : /^\/(extension|integrations)/.test(pathname) ? 'integrations'
    : pathname.startsWith('/admin') ? 'admin' : '';

  const aller = (id: string) => {
    setMenuOpen(false);
    const page = [...liens, { id: 'login', label: '', href: '/login' }].find((l) => l.id === id)?.href;
    if (page) avecFondu(() => navigate(page));
    else if (section) section.onClick(id);
    // Section de l'accueil depuis une autre page : l'accueil y défile à l'arrivée.
    else avecFondu(() => navigate('/home', { state: { section: id } }));
  };

  // 2ᵉ rangée : même fondu ; Ctrl/Maj+clic garde le comportement du navigateur.
  const ouvrir = (e: MouseEvent<HTMLAnchorElement>, href: string) => {
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || href === pathname) return;
    e.preventDefault();
    avecFondu(() => navigate(href));
  };

  // Accueil : ombre au défilement et barre de progression.
  useEffect(() => {
    if (!section) return;
    const onScroll = () => {
      const d = document.documentElement;
      const max = d.scrollHeight - d.clientHeight;
      setScrolled(window.scrollY > 20);
      setProgress(max > 0 ? d.scrollTop / max : 0);
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, [!section]); // eslint-disable-line react-hooks/exhaustive-deps

  // Hauteur réelle de la barre (2ᵉ rangée comprise) → `--nav-total`.
  useLayoutEffect(() => {
    const el = barre.current;
    if (!el) return;
    const racine = document.documentElement.style;
    const publier = () => racine.setProperty('--nav-total', `${el.offsetHeight}px`);
    publier();
    const ro = new ResizeObserver(publier);
    ro.observe(el);
    return () => { ro.disconnect(); racine.removeProperty('--nav-total'); };
  }, []);

  const menu: Lien[] = niveau >= 4 && !user ? [...liens, { id: 'login', label: t('nav.signIn'), href: '/login' }] : liens;
  const avatarLetter = user?.name ? user.name[0].toUpperCase() : (user?.email?.[0].toUpperCase() || '?');
  const crans = Array.from({ length: niveau }, (_, i) => `r${i + 1}`).join(' ');

  return (
    <>
      <header ref={barre} className={`navbar ${scrolled ? 'scrolled' : ''} ${crans}`}>
        {section && <div className="nav-progress" style={{ width: `${progress * 100}%` }} aria-hidden="true" />}

        <div className="nav-inner" ref={ligne}>
          <a
            href="/home" className="nav-logo" aria-label={t('nav.home')}
            onClick={(e) => { e.preventDefault(); if (section) section.onClick('hero'); else avecFondu(() => navigate('/home')); }}
          >
            <img src="/Logo.png" alt="" />
            <span className="animated-logo-text" aria-hidden="true">
              {'récis'.split('').map((c, i) => (
                <span key={i} style={{ animationDelay: `${i / 10}s` }}>{c}</span>
              ))}
            </span>
          </a>

          <nav aria-label={t('nav.menu_label')}>
            <ul className="nav-links">
              {liens.map((l, i) => (
                <li key={l.id} className={l.href && !liens[i - 1]?.href ? 'nav-sep' : undefined}>
                  <a
                    href={l.href ?? `/home#${l.id}`}
                    className={actif === l.id ? 'active' : ''}
                    aria-current={actif === l.id ? (l.href ? 'page' : 'location') : undefined}
                    onClick={(e) => { e.preventDefault(); aller(l.id); }}
                  >{l.label}{l.href && <ArrowUpRight className="nav-ailleurs" size={13} strokeWidth={2.25} aria-hidden="true" />}</a>
                </li>
              ))}
            </ul>
          </nav>

          <div className="lang-toggle" role="group" aria-label={t('nav.language')}>
            <button className={fr ? 'active' : ''} aria-pressed={fr} onClick={() => i18n.changeLanguage('fr')}>FR</button>
            <button className={fr ? '' : 'active'} aria-pressed={!fr} onClick={() => i18n.changeLanguage('en')}>EN</button>
          </div>

          {user ? (
            <button
              className="nav-avatar" onClick={() => (onAccount ? onAccount() : setBiblio(true))}
              title={t('nav.my_account')} aria-label={t('nav.my_account')} aria-haspopup="dialog"
            >{avatarLetter}</button>
          ) : (
            <div className="nav-compte">
              <button className="nav-btn nav-signin" onClick={() => navigate('/login')}>{t('nav.signIn')}</button>
              <button className="nav-btn primary" onClick={() => navigate('/register')}>{t('nav.signUp')}</button>
            </div>
          )}

          <button
            className="hamburger" onClick={() => setMenuOpen((v) => !v)}
            aria-label={t('nav.open_menu')} aria-expanded={menuOpen} aria-controls="mobile-menu"
          >
            <span style={{ transform: menuOpen ? 'rotate(45deg) translate(5px, 5px)' : 'none' }} />
            <span style={{ opacity: menuOpen ? 0 : 1 }} />
            <span style={{ transform: menuOpen ? 'rotate(-45deg) translate(5px, -5px)' : 'none' }} />
          </button>
        </div>

        {sub && (
          <nav className="nav-sub" aria-label={sub.label}>
            <div className="nav-sub-in">
              <strong>{sub.label}</strong>
              <ul>
                {sub.links.map((l) => (
                  <li key={l.href}>
                    <NavLink to={l.href} onClick={(e) => ouvrir(e, l.href)}>{l.label}{l.badge}</NavLink>
                  </li>
                ))}
              </ul>
            </div>
          </nav>
        )}
      </header>

      {/* Hors accueil : bouton flottant vers l'accueil (l'accueil a le sien,
          « Revenir en haut », même place, même style). */}
      {!section && (
        <a
          href="/home" className="retour-haut retour-haut--visible"
          aria-label={t('nav.home')} title={t('nav.home')}
          onClick={(e) => {
            if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
            e.preventDefault(); avecFondu(() => navigate('/home'));
          }}
        >
          <House size={22} strokeWidth={2.2} aria-hidden="true" />
        </a>
      )}

      {user && !onAccount && biblio !== null && (
        <Suspense fallback={null}>
          <BibliothequeHote isOpen={biblio} onClose={() => setBiblio(false)} />
        </Suspense>
      )}

      <MobileMenu
        isOpen={menuOpen && niveau >= 2} links={menu} activeSection={actif}
        onNavClick={aller} onClose={() => setMenuOpen(false)}
      />
    </>
  );
}
