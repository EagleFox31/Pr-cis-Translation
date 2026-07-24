import { useEffect, useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import MobileMenu from './MobileMenu';
import AdminMenu from './AdminMenu';

const logo = "/Logo.png";

interface NavbarProps {
  activeSection: string;
  onNavClick: (sectionId: string) => void;
  onLibraryOpen?: () => void;
}

export default function Navbar({ activeSection, onNavClick, onLibraryOpen }: NavbarProps) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isScrolled, setIsScrolled] = useState(false);
  const [scrollProgress, setScrollProgress] = useState(0);
  const { t, i18n } = useTranslation();
  const navbarRef = useRef<HTMLElement>(null);
  const navigate = useNavigate();
  const { user } = useAuth();

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

  const avatarLetter = user?.name ? user.name[0].toUpperCase() : (user?.email?.[0].toUpperCase() || '?');

  return (
    <>
      <nav ref={navbarRef} className={`navbar ${isScrolled ? 'scrolled' : ''}`}>
        <div style={{ position: 'absolute', bottom: '-1px', left: 0, height: '2px', background: 'linear-gradient(90deg, #1a4dc7, #c9a84c)', width: `${scrollProgress * 100}%`, transition: 'width 0.1s linear', zIndex: 1001 }} />

        <div className="nav-inner">
          <a href="#hero" className="nav-logo" onClick={(e) => { e.preventDefault(); handleClick('hero'); }} style={{ display: 'flex', alignItems: 'center' }}>
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
              const isActive = link.id === 'hero' ? activeSection === 'hero'
                : (activeSection === link.id || (link.id === 'features' && (activeSection === 'features' || activeSection === 'comparison')));
              return (
                <li key={link.id}>
                  <a href={`#${link.id}`} className={isActive ? 'active' : ''} onClick={(e) => { e.preventDefault(); handleClick(link.id); }}>{link.label}</a>
                </li>
              );
            })}
          </ul>

          <div className="lang-toggle">
            <button className={i18n.language === 'fr' ? 'active' : ''} onClick={() => i18n.changeLanguage('fr')}>FR</button>
            <button className={i18n.language === 'en' ? 'active' : ''} onClick={() => i18n.changeLanguage('en')}>EN</button>
          </div>

          {/* Administration — menu déroulant partagé (se rend null hors admin) */}
          <AdminMenu />

          {/* Profil ou Connexion */}
          {user ? (
            <button
              onClick={onLibraryOpen}
              title="Mon compte"
              style={{
                width: '34px', height: '34px', borderRadius: '999px',
                background: 'var(--blue)', color: 'white', border: 'none',
                fontWeight: 700, fontSize: '14px', cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: 'inherit', flexShrink: 0, transition: 'opacity 0.15s',
              }}
            >{avatarLetter}</button>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
              <button onClick={() => navigate('/login')}
                style={{ padding: '7px 14px', borderRadius: '8px', border: '1.5px solid var(--gray-200)', background: 'transparent', color: 'var(--gray-700)', fontWeight: 600, fontSize: '13px', cursor: 'pointer', fontFamily: 'inherit', whiteSpace: 'nowrap', transition: 'all 0.18s ease' }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--blue)'; e.currentTarget.style.color = 'var(--blue)'; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--gray-200)'; e.currentTarget.style.color = 'var(--gray-700)'; }}
              >{t('nav.signIn')}</button>
              <button onClick={() => navigate('/register')}
                style={{ padding: '7px 14px', borderRadius: '8px', border: 'none', background: 'var(--blue)', color: 'white', fontWeight: 600, fontSize: '13px', cursor: 'pointer', fontFamily: 'inherit', whiteSpace: 'nowrap', transition: 'all 0.18s ease' }}
              >{t('nav.signUp')}</button>
            </div>
          )}

          <button className="hamburger" onClick={() => setIsMenuOpen(!isMenuOpen)} aria-label="Toggle menu">
            <span style={{ transform: isMenuOpen ? 'rotate(45deg) translate(5px, 5px)' : 'none' }} />
            <span style={{ opacity: isMenuOpen ? 0 : 1 }} />
            <span style={{ transform: isMenuOpen ? 'rotate(-45deg) translate(5px, -5px)' : 'none' }} />
          </button>
        </div>
      </nav>

      <MobileMenu isOpen={isMenuOpen} links={navLinks} activeSection={activeSection} onNavClick={handleClick} onClose={() => setIsMenuOpen(false)} />
    </>
  );
}
