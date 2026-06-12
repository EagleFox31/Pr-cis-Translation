import { motion, AnimatePresence } from 'motion/react';
import type { ProgressEvent, ProgressStep } from '../../hooks/useTranslationProgress';

interface Step {
  id: ProgressStep;
  label: string;
  labelEn: string;
}

const STEPS: Step[] = [
  { id: 'start',     label: 'Envoi du fichier',           labelEn: 'Uploading file' },
  { id: 'extract',   label: 'Extraction du texte',        labelEn: 'Extracting text' },
  { id: 'translate', label: 'Traduction IA',              labelEn: 'AI translation' },
  { id: 'inject',    label: 'Génération du document',     labelEn: 'Generating document' },
  { id: 'done',      label: 'Terminé',                    labelEn: 'Done' },
];

const STEP_ORDER: ProgressStep[] = ['start', 'extract', 'translate', 'inject', 'done'];

function stepIndex(s: ProgressStep) {
  const i = STEP_ORDER.indexOf(s);
  return i === -1 ? 0 : i;
}

interface TranslationProgressProps {
  progress: ProgressEvent | null;
  lang?: 'fr' | 'en';
}

export default function TranslationProgress({ progress, lang = 'fr' }: TranslationProgressProps) {
  const activeIdx = progress ? stepIndex(progress.step === 'cache' ? 'done' : progress.step) : 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      style={{
        background: 'var(--gray-50)',
        border: '1px solid var(--gray-200)',
        borderRadius: '12px',
        padding: '20px 22px',
        display: 'flex',
        flexDirection: 'column',
        gap: '14px',
      }}
    >
      {/* Steps list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {STEPS.map((step, i) => {
          const isDone = i < activeIdx;
          const isActive = i === activeIdx;
          const isPending = i > activeIdx;

          return (
            <div key={step.id} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              {/* Icon */}
              <div
                style={{
                  width: '26px',
                  height: '26px',
                  borderRadius: '50%',
                  flexShrink: 0,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: isDone
                    ? '#dcfce7'
                    : isActive
                    ? 'var(--blue)'
                    : 'var(--gray-200)',
                  transition: 'background 0.3s ease',
                }}
              >
                {isDone ? (
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20 6L9 17l-5-5" />
                  </svg>
                ) : isActive ? (
                  <motion.span
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1.1, repeat: Infinity, ease: 'linear' }}
                    style={{ display: 'inline-flex' }}
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
                      <circle cx="12" cy="12" r="10" opacity="0.25" />
                      <path d="M12 2a10 10 0 0 1 10 10" strokeLinecap="round" />
                    </svg>
                  </motion.span>
                ) : (
                  <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: 'var(--gray-400)' }} />
                )}
              </div>

              {/* Label + progress bar */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  fontSize: '13px',
                  fontWeight: isActive ? 600 : 500,
                  color: isDone ? '#16a34a' : isActive ? 'var(--navy)' : 'var(--gray-500)',
                  transition: 'color 0.3s ease',
                  marginBottom: isActive && step.id === 'translate' && progress?.total ? '5px' : '0',
                }}>
                  {lang === 'fr' ? step.label : step.labelEn}
                  {isDone && step.id !== 'done' && (
                    <span style={{ fontSize: '11px', marginLeft: '6px', color: '#16a34a', fontWeight: 400 }}>✓</span>
                  )}
                </div>

                {/* Barre de progression page par page pour extract et translate */}
                <AnimatePresence>
                  {isActive && progress?.total && (progress.step === 'extract' || progress.step === 'translate') && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div style={{
                          flex: 1,
                          height: '4px',
                          background: 'var(--gray-200)',
                          borderRadius: '2px',
                          overflow: 'hidden',
                        }}>
                          <motion.div
                            style={{ height: '100%', background: 'var(--blue)', borderRadius: '2px' }}
                            initial={{ width: '0%' }}
                            animate={{ width: `${Math.round(((progress.page ?? 0) / progress.total) * 100)}%` }}
                            transition={{ duration: 0.4, ease: 'easeOut' }}
                          />
                        </div>
                        <span style={{ fontSize: '11px', color: 'var(--gray-500)', flexShrink: 0, fontVariantNumeric: 'tabular-nums' }}>
                          {progress.page ?? 0} / {progress.total}
                        </span>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>
          );
        })}
      </div>

      {/* Message courant */}
      <AnimatePresence mode="wait">
        {progress && progress.step !== 'done' && (
          <motion.p
            key={progress.message}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            style={{
              fontSize: '11.5px',
              color: 'var(--gray-500)',
              marginTop: '2px',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {progress.message}
          </motion.p>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
