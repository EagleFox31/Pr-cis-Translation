import { useEffect, useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import MobileMenu from './MobileMenu';

const logo = "/Logo.png";

interface NavbarProps {
  activeSection: string;
  onNavClick: (sectionId: string) => void;
}

export default function Navbar({ activeSection, onNavClick }: NavbarProps) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isScrolled, setIsScrolled] = useState(false);
  const [scrollProgress, setScrollProgress] = useState(0);
  const { t, i18n } = useTranslation();
  const navbarRef = useRef<HTMLElement>(null);

  // Ordre aligné sur les sections de la page (SRS RF-1)
  const navLinks = [
    { id: 'hero', label: t('nav.home') },
    { id: 'story', label: t('nav.howItWorks') },
    { id: 'features', label: t('nav.features') },
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

  return (
    <>
      <nav ref={navbarRef} className={`navbar ${isScrolled ? 'scrolled' : ''}`}>
        {/* Reading progress bar */}
        <div
          style={{
            position: 'absolute',
            bottom: '-1px',
            left: 0,
            height: '2px',
            background: 'linear-gradient(90deg, #1a4dc7, #c9a84c)',
            width: `${scrollProgress * 100}%`,
            transition: 'width 0.1s linear',
            zIndex: 1001,
          }}
        />

        <div className="nav-inner">
          <a
            href="#hero"
            className="nav-logo"
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
                  <a
                    href={`#${link.id}`}
                    className={isActive ? 'active' : ''}
                    onClick={(e) => { e.preventDefault(); handleClick(link.id); }}
                  >
                    {link.label}
                  </a>
                </li>
              );
            })}
          </ul>

          <div className="lang-toggle">
            <button
              className={i18n.language === 'fr' ? 'active' : ''}
              onClick={() => i18n.changeLanguage('fr')}
            >
              FR
            </button>
            <button
              className={i18n.language === 'en' ? 'active' : ''}
              onClick={() => i18n.changeLanguage('en')}
            >
              EN
            </button>
          </div>

          <button
            className="hamburger"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            aria-label="Toggle menu"
          >
            <span style={{ transform: isMenuOpen ? 'rotate(45deg) translate(5px, 5px)' : 'none' }} />
            <span style={{ opacity: isMenuOpen ? 0 : 1 }} />
            <span style={{ transform: isMenuOpen ? 'rotate(-45deg) translate(5px, -5px)' : 'none' }} />
          </button>
        </div>
      </nav>

      <MobileMenu
        isOpen={isMenuOpen}
        links={navLinks}
        activeSection={activeSection}
        onNavClick={handleClick}
        onClose={() => setIsMenuOpen(false)}
      />
    </>
  );
}
