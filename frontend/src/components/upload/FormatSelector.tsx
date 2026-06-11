import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';

export interface FormatOption {
  key: string;
  label: string;
  desc: string;
  icon: string;
}

interface FormatSelectorProps {
  options: FormatOption[];
  current: string;
  onChange: (key: string) => void;
}

export default function FormatSelector({ options, current, onChange }: FormatSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);

  const currentOption = options.find((o) => o.key === current) || options[0];

  return (
    <div style={{ position: 'relative' }}>
      <label
        style={{
          fontSize: '11px',
          fontWeight: 600,
          color: 'var(--navy)',
          display: 'block',
          marginBottom: '5px',
          letterSpacing: '0.03em',
        }}
      >
        Mode de traduction
      </label>
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '8px',
          padding: '10px 14px',
          borderRadius: '10px',
          border: '1px solid var(--gray-300)',
          background: '#f8fafc',
          cursor: 'pointer',
          fontSize: '13px',
          color: 'var(--navy)',
          fontWeight: 500,
          fontFamily: 'inherit',
          transition: 'border-color 0.2s',
        }}
        onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--blue)'; }}
        onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--gray-300)'; }}
      >
        <span>{currentOption.icon} {currentOption.label}</span>
        <motion.span
          animate={{ rotate: isOpen ? 180 : 0 }}
          transition={{ duration: 0.2 }}
          style={{ color: '#94a3b8' }}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </motion.span>
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.96 }}
            transition={{ duration: 0.15, ease: 'easeOut' }}
            style={{
              position: 'absolute',
              top: '100%',
              left: 0,
              right: 0,
              marginTop: '4px',
              background: 'var(--white)',
              border: '1px solid var(--gray-200)',
              borderRadius: '10px',
              boxShadow: '0 8px 24px rgba(0,0,0,0.08)',
              zIndex: 50,
              overflow: 'hidden',
            }}
          >
            {options.map((opt) => (
              <button
                key={opt.key}
                onClick={() => { onChange(opt.key); setIsOpen(false); }}
                style={{
                  display: 'block',
                  width: '100%',
                  textAlign: 'left',
                  padding: '10px 14px',
                  border: 'none',
                  background: opt.key === current ? 'var(--gray-50)' : 'transparent',
                  cursor: 'pointer',
                  fontSize: '13px',
                  color: 'var(--navy)',
                  fontFamily: 'inherit',
                  transition: 'background 0.15s',
                  borderLeft: opt.key === current ? '3px solid var(--blue)' : '3px solid transparent',
                }}
                onMouseEnter={(e) => { if (opt.key !== current) e.currentTarget.style.background = '#f8fafc'; }}
                onMouseLeave={(e) => { if (opt.key !== current) e.currentTarget.style.background = 'transparent'; }}
              >
                <div style={{ fontWeight: opt.key === current ? 600 : 400 }}>
                  {opt.icon} {opt.label}
                </div>
                <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>{opt.desc}</div>
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
