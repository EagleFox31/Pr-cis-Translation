import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'motion/react';
import { useTranslation } from 'react-i18next';
import {
  Home, Sparkles, Workflow, Tag, Info, ShieldCheck, Puzzle, Code2, Users, FileText,
  LifeBuoy, ScrollText, FlaskConical, Scale, Lock, Cookie, ChevronRight, Globe, type LucideIcon,
} from 'lucide-react';

interface MobileMenuProps {
  isOpen: boolean;
  links: Array<{ id: string; label: string; href?: string }>;
  activeSection: string;
  onNavClick: (sectionId: string) => void;
  onClose: () => void;
}

/** Icône d'un lien d'après son identifiant (section de l'accueil ou chemin). */
const ICONES: Array<[RegExp, LucideIcon]> = [
  [/^hero$/, Home], [/^features$/, Sparkles], [/^story$/, Workflow], [/^pricing$/, Tag],
  [/^about$/, Info], [/^admin$/, ShieldCheck], [/extension/, Puzzle], [/api/, Code2],
  [/users/, Users], [/documents/, FileText], [/support/, LifeBuoy], [/logs/, ScrollText],
  [/beta/, FlaskConical], [/mentions|conditions/, Scale], [/confidentialite/, Lock], [/cookies/, Cookie],
];
const icone = (id: string): LucideIcon => ICONES.find(([re]) => re.test(id))?.[1] ?? FileText;

export default function MobileMenu({ isOpen, links, activeSection, onNavClick, onClose }: MobileMenuProps) {
  const { pathname } = useLocation();
  const fermer = useRef(onClose);
  fermer.current = onClose;

  // Changement de page par un autre chemin que le menu (retour arrière, lien
  // dans la page) : le menu ne reste pas ouvert par-dessus la nouvelle page.
  useEffect(() => { fermer.current(); }, [pathname]);

  // Échap ferme le menu et rend le focus au bouton ☰.
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      fermer.current();
      document.querySelector<HTMLElement>('.hamburger')?.focus();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [isOpen]);

  const { t, i18n } = useTranslation();
  const langue = i18n.language?.startsWith('en') ? 'en' : 'fr';
  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
          className="mobile-menu open"
          id="mobile-menu"
        >
          <nav className="mm-links">
            {links.map((link) => {
              const isActive = link.id === 'hero'
                ? activeSection === 'hero'
                : (activeSection === link.id || (link.id === 'features' && activeSection === 'comparison'));
              const Icone = icone(link.id);
              return (
                <a
                  key={link.id}
                  href={link.href ?? `#${link.id}`}
                  className={`mm-link${isActive ? ' active' : ''}`}
                  aria-current={isActive ? 'page' : undefined}
                  onClick={(e) => { e.preventDefault(); onNavClick(link.id); }}
                >
                  <span className="mm-ico"><Icone size={18} strokeWidth={2} aria-hidden="true" /></span>
                  <span className="mm-label">{link.label}</span>
                  <ChevronRight className="mm-chev" size={16} strokeWidth={2} aria-hidden="true" />
                </a>
              );
            })}
          </nav>
          <div className="mm-lang">
            <span className="mm-lang-title"><Globe size={16} strokeWidth={2} aria-hidden="true" />{t('nav.language')}</span>
            <div className="mm-seg" role="group" aria-label={t('nav.language')}>
              {(['fr', 'en'] as const).map((l) => (
                <button key={l} className={langue === l ? 'active' : ''} aria-pressed={langue === l}
                  aria-label={l === 'fr' ? 'Français' : 'English'}
                  onClick={() => i18n.changeLanguage(l)}>{l.toUpperCase()}</button>
              ))}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
