import { useEffect, useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import MobileMenu from './MobileMenu';

const logo = "/Logo.png";

interface NavbarProps {
  activeSection: string;
  onNavClick: (sectionId: string) => void;
  docCount?: number;
  onLibraryOpen?: () => void;
}

export default function Navbar({ activeSection, onNavClick, docCount = 0, onLibraryOpen }: NavbarProps) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isScrolled, setIsScrolled] = useState(false);
  const [scrollProgress, setScrollProgress] = useState(0);
  const { t, i18n } = useTranslation();
  const navbarRef = useRef<HTMLElement>(null);
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const navLinks = [
    { id: 'hero', label: t('nav.home') },
    { id: 'features', label: t('nav.features') },
    { id: 'story', label: t('nav.howItWorks') },
    { id: 'pricing', label: t('nav.pricing') },
    { id: 'about', label: t('nav.about') },
  ];

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 20);
      const docEl = document.documentElement;
      const scrollTop = docEl.scrollTop;
      const scrollHeight = docEl.scrollHeight - docEl.clientHeight;
      setScrollProgress(scrollHeight > 0 ? scrollTop / scrollHeight : 0);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const handleClick = (sectionId: string) => {
    setIsMenuOpen(false);
    onNavClick(sectionId);
  };

  // Icône avatar : initiales si pas d'avatar
  const avatarLetter = user?.name ? user.name[0].toUpperCase() : (user?.email?.[0].toUpperCase() || '?');

  return (
    <>
      <nav ref={navbarRef} className={`navbar ${isScrolled ? 'scrolled' : ''}`}>
        <div
          style={{
            position: 'absolute', bottom: '-1px', left: 0, height: '2px',
            background: 'linear-gradient(90deg, #1a4dc7, #c9a84c)',
            width: `${scrollProgress * 100}%`, transition: 'width 0.1s linear', zIndex: 1001,
          }}
        />

        <div className="nav-inner">
          <a href="#hero" className="nav-logo"
            onClick={(e) => { e.preventDefault(); handleClick('hero'); }}
            style={{ display: 'flex', alignItems: 'center' }}
          >
            <img src={logo} alt="P" className="h-[46px] w-auto" />
            <span className="animated-logo-text">
              <span style={{ animationDelay: '0.0s' }}>r</span>
              <span style={{ animationDelay: '0.1s' }}>é</span>
              <span style={{ animationDelay: '0.2s' }}>c</span>
              <span style={{ animationDelay: '0.3s' }}>i</span>
              <span style={{ animationDelay: '0.4s' }}>s</span>
            </span>
          </a>

          <ul className="nav-links">
            {navLinks.map((link) => {
              const isActive = link.id === 'hero'
                ? activeSection === 'hero'
                : (activeSection === link.id || (link.id === 'features' && (activeSection === 'features' || activeSection === 'comparison')));
              return (
                <li key={link.id}>
                  <a href={`#${link.id}`} className={isActive ? 'active' : ''}
                    onClick={(e) => { e.preventDefault(); handleClick(link.id); }}>
                    {link.label}
                  </a>
                </li>
              );
            })}
          </ul>

          {/* Bouton bibliothèque */}
          <button onClick={onLibraryOpen} title="Mes documents traduits"
            style={{
              display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px',
              borderRadius: '8px', border: '1.5px solid var(--gray-200)', background: 'transparent',
              cursor: 'pointer', fontSize: '13px', fontWeight: 500, color: 'var(--gray-700)',
              fontFamily: 'inherit', transition: 'all 0.18s ease', position: 'relative',
            }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--blue)'; e.currentTarget.style.color = 'var(--blue)'; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--gray-200)'; e.currentTarget.style.color = 'var(--gray-700)'; }}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14 2 14 8 20 8" />
            </svg>
            <span style={{ display: 'none' }} className="nav-lib-label">{t('nav.library')}</span>
            {docCount > 0 && (
              <span style={{
                position: 'absolute', top: '-6px', right: '-6px', background: 'var(--blue)',
                color: 'white', fontSize: '10px', fontWeight: 700, borderRadius: '999px',
                minWidth: '18px', height: '18px', display: 'flex', alignItems: 'center',
                justifyContent: 'center', padding: '0 4px', border: '2px solid white',
              }}>
                {docCount > 99 ? '99+' : docCount}
              </span>
            )}
          </button>

          {/* Connexion / Compte */}
          {user ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span
                style={{
                  background: 'var(--blue-light)', color: 'var(--blue)',
                  fontSize: '11px', fontWeight: 600, padding: '3px 8px', borderRadius: '6px',
                  textTransform: 'uppercase', letterSpacing: '0.03em',
                }}
              >{user.plan}</span>
              <button
                onClick={() => navigate('/login')}
                style={{
                  width: '32px', height: '32px', borderRadius: '999px',
                  background: 'var(--blue)', color: 'white', border: 'none',
                  fontWeight: 700, fontSize: '13px', cursor: 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontFamily: 'inherit',
                }}
                title={user.email}
              >{avatarLetter}</button>
            </div>
          ) : (
            <button
              onClick={() => navigate('/login')}
              className="nav-cta"
              style={{
                padding: '8px 16px', borderRadius: '8px', border: 'none',
                background: 'var(--blue)', color: 'white', fontWeight: 600,
                fontSize: '13px', cursor: 'pointer', fontFamily: 'inherit',
                transition: 'all 0.18s ease',
              }}
            >{t('nav.signIn')}</button>
          )}

          <div className="lang-toggle">
            <button className={i18n.language === 'fr' ? 'active' : ''} onClick={() => i18n.changeLanguage('fr')}>FR</button>
            <button className={i18n.language === 'en' ? 'active' : ''} onClick={() => i18n.changeLanguage('en')}>EN</button>
          </div>

          <button className="hamburger" onClick={() => setIsMenuOpen(!isMenuOpen)} aria-label="Toggle menu">
            <span style={{ transform: isMenuOpen ? 'rotate(45deg) translate(5px, 5px)' : 'none' }} />
            <span style={{ opacity: isMenuOpen ? 0 : 1 }} />
            <span style={{ transform: isMenuOpen ? 'rotate(-45deg) translate(5px, -5px)' : 'none' }} />
          </button>
        </div>
      </nav>

      <MobileMenu isOpen={isMenuOpen} links={navLinks} activeSection={activeSection}
        onNavClick={handleClick} onClose={() => setIsMenuOpen(false)} />
    </>
  );
}