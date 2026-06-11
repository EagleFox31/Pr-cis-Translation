import { motion, AnimatePresence } from 'motion/react';

interface MobileMenuProps {
  isOpen: boolean;
  links: Array<{ id: string; label: string }>;
  activeSection: string;
  onNavClick: (sectionId: string) => void;
  onClose: () => void;
}

export default function MobileMenu({ isOpen, links, activeSection, onNavClick, onClose }: MobileMenuProps) {
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
          {links.map((link) => {
            const isActive = link.id === 'hero'
              ? activeSection === 'hero'
              : (activeSection === link.id || (link.id === 'features' && activeSection === 'comparison'));
            return (
              <a
                key={link.id}
                href={`#${link.id}`}
                onClick={(e) => { e.preventDefault(); onNavClick(link.id); }}
                style={{
                  color: isActive ? '#1a4dc7' : undefined,
                  fontWeight: isActive ? 700 : 500,
                }}
              >
                {link.label}
              </a>
            );
          })}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
