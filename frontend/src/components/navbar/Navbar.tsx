import { useEffect, useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import MobileMenu from './MobileMenu';

const logo = "/Logo.png";

const PLAN_LABELS: Record<string, string> = {
  free: 'Gratuit',
  starter: 'Starter',
  pro: 'Pro',
  enterprise: 'Enterprise',
  admin: 'Admin',
};

interface NavbarProps {
  activeSection: string;
  onNavClick: (sectionId: string) => void;
  docCount?: number;
  onLibraryOpen?: () => void;
}

export default function Navbar({ activeSection, onNavClick, docCount = 0, onLibraryOpen }: NavbarProps) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
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

  function formatBytes(bytes: number): string {
    if (bytes >= 1_073_741_824) return `${(bytes / 1_073_741_824).toFixed(1)} Go`;
    if (bytes >= 1_048_576) return `${(bytes / 1_048_576).toFixed(0)} Mo`;
    return `${(bytes / 1024).toFixed(0)} Ko`;
  }

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

          <div className="lang-toggle">
            <button className={i18n.language === 'fr' ? 'active' : ''} onClick={() => i18n.changeLanguage('fr')}>FR</button>
            <button className={i18n.language === 'en' ? 'active' : ''} onClick={() => i18n.changeLanguage('en')}>EN</button>
          </div>

          {/* Connexion / Compte */}
          {user ? (
            <div style={{ position: 'relative' }}>
              <button
                onClick={() => setMenuOpen(!menuOpen)}
                style={{
                  display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 8px 4px 4px',
                  borderRadius: '999px', border: '1.5px solid var(--gray-200)', background: 'white',
                  cursor: 'pointer', fontFamily: 'inherit', transition: 'all 0.18s ease',
                }}
                onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--blue)'}
                onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--gray-200)'}
              >
                <span style={{
                  width: '28px', height: '28px', borderRadius: '999px',
                  background: 'var(--blue)', color: 'white', fontWeight: 700,
                  fontSize: '12px', display: 'flex', alignItems: 'center',
                  justifyContent: 'center', flexShrink: 0,
                }}>{avatarLetter}</span>
                <svg width="10" height="6" viewBox="0 0 10 6" fill="none" stroke="var(--gray-500)" strokeWidth="1.5" strokeLinecap="round">
                  <path d="M1 1l4 4 4-4" />
                </svg>
              </button>
              {menuOpen && (
                <>
                  <div style={{ position: 'fixed', inset: 0, zIndex: 998 }} onClick={() => setMenuOpen(false)} />
                  <div style={{
                    position: 'absolute', top: 'calc(100% + 8px)', right: 0,
                    background: 'white', borderRadius: '12px', border: '1px solid var(--gray-200)',
                    boxShadow: '0 12px 32px rgba(0,0,0,.08)', zIndex: 999,
                    minWidth: '220px', padding: '6px', fontFamily: 'inherit',
                  }}>
                    <div style={{ padding: '10px 12px' }}>
                      <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--gray-900)', marginBottom: '1px' }}>
                        {user.name || user.email}
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--gray-500)' }}>{user.email}</div>
                    </div>
                    <div style={{ height: '1px', background: 'var(--gray-100)', margin: '4px 0' }} />
                    <div style={{ padding: '8px 12px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                        <span style={{ fontSize: '12px', color: 'var(--gray-500)' }}>Forfait</span>
                        <span style={{
                          background: user.plan === 'free' ? 'var(--gray-100)' : 'var(--blue-light)',
                          color: user.plan === 'free' ? 'var(--gray-500)' : 'var(--blue)',
                          fontSize: '10px', fontWeight: 700, padding: '2px 7px',
                          borderRadius: '5px', textTransform: 'uppercase', letterSpacing: '0.04em',
                        }}>{PLAN_LABELS[user.plan] || user.plan}</span>
                      </div>
                      {user.storage_limit > 0 ? (
                        <>
                          <div style={{ fontSize: '12px', color: 'var(--gray-400)' }}>
                            {formatBytes(user.storage_used)} / {formatBytes(user.storage_limit)}
                          </div>
                          <div style={{ height: '3px', background: 'var(--gray-100)', borderRadius: '2px', marginTop: '5px' }}>
                            <div style={{
                              height: '3px', borderRadius: '2px', background: 'var(--blue)',
                              width: `${Math.min(100, (user.storage_used / user.storage_limit) * 100)}%`,
                              transition: 'width 0.3s ease',
                            }} />
                          </div>
                        </>
                      ) : user.plan === 'admin' ? (
                        <div style={{ fontSize: '11px', color: 'var(--gray-400)' }}>
                          {formatBytes(user.storage_used)} · Illimité
                        </div>
                      ) : (
                        <div style={{ fontSize: '11px', color: 'var(--gray-400)', fontStyle: 'italic' }}>
                          Traduction seule
                        </div>
                      )}
                    </div>
                    <div style={{ height: '1px', background: 'var(--gray-100)', margin: '4px 0' }} />
                    <button
                      onClick={() => { setMenuOpen(false); logout(); }}
                      style={{
                        width: '100%', display: 'flex', alignItems: 'center', gap: '8px',
                        padding: '8px 12px', borderRadius: '7px', border: 'none',
                        background: 'transparent', cursor: 'pointer', fontFamily: 'inherit',
                        fontSize: '13px', color: 'var(--gray-600)', transition: 'all 0.12s ease',
                      }}
                      onMouseEnter={e => { e.currentTarget.style.background = 'var(--gray-50)'; e.currentTarget.style.color = '#dc2626'; }}
                      onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--gray-600)'; }}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4m7 14l5-5-5-5m5 5H9" />
                      </svg>
                      {t('nav.logout')}
                    </button>
                  </div>
                </>
              )}
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
              <button
                onClick={() => navigate('/login')}
                style={{
                  padding: '7px 14px', borderRadius: '8px', border: '1.5px solid var(--gray-200)',
                  background: 'transparent', color: 'var(--gray-700)', fontWeight: 600,
                  fontSize: '13px', cursor: 'pointer', fontFamily: 'inherit', whiteSpace: 'nowrap',
                  transition: 'all 0.18s ease',
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--blue)'; e.currentTarget.style.color = 'var(--blue)'; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--gray-200)'; e.currentTarget.style.color = 'var(--gray-700)'; }}
              >{t('nav.signIn')}</button>
              <button
                onClick={() => navigate('/register')}
                style={{
                  padding: '7px 14px', borderRadius: '8px', border: 'none',
                  background: 'var(--blue)', color: 'white', fontWeight: 600,
                  fontSize: '13px', cursor: 'pointer', fontFamily: 'inherit', whiteSpace: 'nowrap',
                  transition: 'all 0.18s ease',
                }}
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

      <MobileMenu isOpen={isMenuOpen} links={navLinks} activeSection={activeSection}
        onNavClick={handleClick} onClose={() => setIsMenuOpen(false)} />
    </>
  );
}