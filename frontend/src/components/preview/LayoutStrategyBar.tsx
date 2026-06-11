import { motion } from 'motion/react';

export type LayoutMode = 'auto' | 'reflow' | 'shrink';
export type ShrinkScope = 'page' | 'document';

interface LayoutStrategyBarProps {
  currentPage: number;
  /** Mode effectif appliqué à la page courante. */
  pageMode: LayoutMode;
  onPageModeChange: (mode: LayoutMode) => void;
  /** Portée de la réduction de police (visible seulement si un mode "shrink" est utilisé). */
  shrinkScope: ShrinkScope;
  onScopeChange: (scope: ShrinkScope) => void;
  /** Au moins une page utilise le mode "réduire" → on affiche le sélecteur de portée. */
  shrinkUsed: boolean;
  /** Des changements non appliqués sont en attente. */
  dirty: boolean;
  isRegenerating: boolean;
  onApply: () => void;
}

const MODES: { key: LayoutMode; label: string; icon: string; desc: string }[] = [
  { key: 'auto', label: 'Auto', icon: '✨', desc: 'Combinaison automatique (ajuste puis réduit si besoin)' },
  { key: 'reflow', label: 'Ajuster les blocs', icon: '↔', desc: 'Déplace/élargit les blocs, sans réduire la police' },
  { key: 'shrink', label: 'Réduire la taille', icon: '🅰', desc: 'Garde les positions, réduit la police uniformément' },
];

export default function LayoutStrategyBar({
  currentPage,
  pageMode,
  onPageModeChange,
  shrinkScope,
  onScopeChange,
  shrinkUsed,
  dirty,
  isRegenerating,
  onApply,
}: LayoutStrategyBarProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '10px',
        padding: '8px 12px',
        borderRadius: '10px',
        background: '#f8fafc',
        border: '1px solid var(--gray-200, #e5e7eb)',
        fontSize: '12px',
      }}
    >
      <span style={{ fontWeight: 600, color: 'var(--navy, #0d1b3e)', whiteSpace: 'nowrap' }}>
        Mise en page · page {currentPage}
      </span>

      {/* Segmented mode selector (applies to the current page) */}
      <div style={{ display: 'inline-flex', borderRadius: '8px', overflow: 'hidden', border: '1px solid var(--gray-300, #d1d5db)' }}>
        {MODES.map((m) => {
          const active = m.key === pageMode;
          return (
            <button
              key={m.key}
              title={m.desc}
              onClick={() => onPageModeChange(m.key)}
              style={{
                padding: '6px 12px',
                border: 'none',
                borderLeft: m.key !== 'auto' ? '1px solid var(--gray-300, #d1d5db)' : 'none',
                background: active ? 'var(--blue, #2563eb)' : 'white',
                color: active ? 'white' : 'var(--navy, #0d1b3e)',
                fontWeight: active ? 600 : 500,
                fontSize: '12px',
                cursor: 'pointer',
                fontFamily: 'inherit',
                whiteSpace: 'nowrap',
                transition: 'background 0.15s',
              }}
            >
              {m.icon} {m.label}
            </button>
          );
        })}
      </div>

      {/* Scope selector — only meaningful when a "réduire" mode is in play */}
      {shrinkUsed && (
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ color: '#64748b' }}>Réduction&nbsp;:</span>
          <div style={{ display: 'inline-flex', borderRadius: '8px', overflow: 'hidden', border: '1px solid var(--gray-300, #d1d5db)' }}>
            {(['page', 'document'] as ShrinkScope[]).map((sc) => {
              const active = sc === shrinkScope;
              return (
                <button
                  key={sc}
                  onClick={() => onScopeChange(sc)}
                  title={sc === 'page' ? 'Réduire seulement cette page' : 'Taille de police homogène sur tout le document'}
                  style={{
                    padding: '6px 10px',
                    border: 'none',
                    borderLeft: sc === 'document' ? '1px solid var(--gray-300, #d1d5db)' : 'none',
                    background: active ? 'var(--navy, #0d1b3e)' : 'white',
                    color: active ? 'white' : 'var(--navy, #0d1b3e)',
                    fontWeight: active ? 600 : 500,
                    fontSize: '12px',
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                    transition: 'background 0.15s',
                  }}
                >
                  {sc === 'page' ? 'cette page' : 'tout le doc'}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Apply / regenerate */}
      <motion.button
        whileHover={dirty && !isRegenerating ? { scale: 1.03 } : {}}
        whileTap={dirty && !isRegenerating ? { scale: 0.97 } : {}}
        onClick={onApply}
        disabled={!dirty || isRegenerating}
        style={{
          marginLeft: 'auto',
          padding: '7px 16px',
          borderRadius: '8px',
          border: 'none',
          background: dirty && !isRegenerating ? 'var(--blue, #2563eb)' : 'var(--gray-300, #d1d5db)',
          color: 'white',
          fontWeight: 600,
          fontSize: '12px',
          cursor: dirty && !isRegenerating ? 'pointer' : 'not-allowed',
          fontFamily: 'inherit',
          display: 'inline-flex',
          alignItems: 'center',
          gap: '6px',
          whiteSpace: 'nowrap',
        }}
      >
        {isRegenerating ? (
          <>
            <motion.span
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
              style={{ display: 'inline-flex' }}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <circle cx="12" cy="12" r="10" opacity="0.25" />
                <path d="M12 2a10 10 0 0 1 10 10" strokeLinecap="round" />
              </svg>
            </motion.span>
            Régénération…
          </>
        ) : (
          <>↻ Appliquer</>
        )}
      </motion.button>
    </div>
  );
}
