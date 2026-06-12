import { useTranslation } from 'react-i18next';
import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';

interface LanguageOption {
  code: string;
  label: string;
  flag: string;
}

interface LanguageSelectorProps {
  sourceLang: string;
  targetLang: string;
  onSourceChange: (code: string) => void;
  onTargetChange: (code: string) => void;
  onSwap: () => void;
  showSource?: boolean;
}

const languages: LanguageOption[] = [
  // Détection automatique
  { code: 'auto', label: 'Détection automatique', flag: '🌐' },

  // English variants
  { code: 'en-US', label: 'English (US)', flag: '🇺🇸' },
  { code: 'en-GB', label: 'English (UK)', flag: '🇬🇧' },
  { code: 'en-CA', label: 'English (Canada)', flag: '🇨🇦' },
  { code: 'en-AU', label: 'English (Australia)', flag: '🇦🇺' },

  // French variants
  { code: 'fr-FR', label: 'Français (France)', flag: '🇫🇷' },
  { code: 'fr-CA', label: 'Français (Canada)', flag: '🇨🇦' },
  { code: 'fr-BE', label: 'Français (Belgique)', flag: '🇧🇪' },
  { code: 'fr-CH', label: 'Français (Suisse)', flag: '🇨🇭' },

  // Spanish variants
  { code: 'es-ES', label: 'Español (España)', flag: '🇪🇸' },
  { code: 'es-MX', label: 'Español (México)', flag: '🇲🇽' },
  { code: 'es-AR', label: 'Español (Argentina)', flag: '🇦🇷' },
  { code: 'es-CO', label: 'Español (Colombia)', flag: '🇨🇴' },

  // German variants
  { code: 'de-DE', label: 'Deutsch (Deutschland)', flag: '🇩🇪' },
  { code: 'de-AT', label: 'Deutsch (Österreich)', flag: '🇦🇹' },
  { code: 'de-CH', label: 'Deutsch (Schweiz)', flag: '🇨🇭' },

  // Italian
  { code: 'it-IT', label: 'Italiano', flag: '🇮🇹' },

  // Portuguese variants
  { code: 'pt-PT', label: 'Português (Portugal)', flag: '🇵🇹' },
  { code: 'pt-BR', label: 'Português (Brasil)', flag: '🇧🇷' },

  // Dutch
  { code: 'nl-NL', label: 'Nederlands', flag: '🇳🇱' },
  { code: 'nl-BE', label: 'Nederlands (België)', flag: '🇧🇪' },

  // Nordic
  { code: 'sv-SE', label: 'Svenska', flag: '🇸🇪' },
  { code: 'da-DK', label: 'Dansk', flag: '🇩🇰' },
  { code: 'nb-NO', label: 'Norsk (Bokmål)', flag: '🇳🇴' },
  { code: 'fi-FI', label: 'Suomi', flag: '🇫🇮' },

  // Other European
  { code: 'pl-PL', label: 'Polski', flag: '🇵🇱' },
  { code: 'cs-CZ', label: 'Čeština', flag: '🇨🇿' },
  { code: 'hu-HU', label: 'Magyar', flag: '🇭🇺' },
  { code: 'ro-RO', label: 'Română', flag: '🇷🇴' },
  { code: 'el-GR', label: 'Ελληνικά', flag: '🇬🇷' },
  { code: 'tr-TR', label: 'Türkçe', flag: '🇹🇷' },

  // Arabic
  { code: 'ar-SA', label: 'العربية', flag: '🇸🇦' },

  // Russian
  { code: 'ru-RU', label: 'Русский', flag: '🇷🇺' },

  // Asian
  { code: 'zh-CN', label: '中文 (简体)', flag: '🇨🇳' },
  { code: 'zh-TW', label: '中文 (繁體)', flag: '🇹🇼' },
  { code: 'ja-JP', label: '日本語', flag: '🇯🇵' },
  { code: 'ko-KR', label: '한국어', flag: '🇰🇷' },
];

const sourceLanguages = languages.filter((l) => l.code !== 'auto');
const targetLanguages = languages.filter((l) => l.code !== 'auto');

function CustomSelect({
  value,
  onChange,
  label,
  options,
  exclude,
  showAuto,
}: {
  value: string;
  onChange: (v: string) => void;
  label: string;
  options: LanguageOption[];
  exclude?: string;
  showAuto?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const filtered = exclude
    ? options.filter((l) => l.code !== exclude)
    : options;

  const selected = value === 'auto' && showAuto
    ? { code: 'auto', label: 'Détection automatique', flag: '🌐' }
    : filtered.find((l) => l.code === value) || filtered[0];

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setIsOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={ref} style={{ flex: 1 }}>
      <label
        style={{
          fontSize: '10px',
          fontWeight: 700,
          color: 'var(--gray-400)',
          display: 'block',
          marginBottom: '6px',
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
        }}
      >
        {label}
      </label>
      <div style={{ position: 'relative' }}>
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          style={{
            width: '100%',
            padding: '10px 32px 10px 12px',
            borderRadius: '12px',
            border: isOpen ? '1.5px solid var(--blue)' : '1.5px solid var(--gray-200)',
            fontSize: '13.5px',
            fontWeight: 500,
            background: 'var(--white)',
            color: 'var(--navy)',
            cursor: 'pointer',
            fontFamily: 'var(--font-body)',
            textAlign: 'left',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            outline: 'none',
            boxShadow: isOpen ? '0 0 0 3px rgba(37,99,235,0.08)' : 'none',
            transition: 'border-color 0.15s, box-shadow 0.15s',
          }}
        >
          <span style={{ fontSize: '16px', flexShrink: 0 }}>{selected?.flag}</span>
          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {selected?.label}
          </span>
          <motion.span
            animate={{ rotate: isOpen ? 180 : 0 }}
            transition={{ duration: 0.2 }}
            style={{ color: 'var(--gray-400)', flexShrink: 0 }}
          >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </motion.span>
        </button>

        <AnimatePresence>
          {isOpen && (
            <motion.div
              initial={{ opacity: 0, y: -6, scale: 0.96 }}
              animate={{ opacity: 1, y: 4, scale: 1 }}
              exit={{ opacity: 0, y: -6, scale: 0.96 }}
              transition={{ duration: 0.15, ease: 'easeOut' }}
              style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                right: 0,
                zIndex: 100,
                background: 'var(--white)',
                border: '1px solid var(--gray-200)',
                borderRadius: '12px',
                boxShadow: '0 12px 32px rgba(0,0,0,0.10)',
                overflow: 'hidden',
                maxHeight: '280px',
                overflowY: 'auto',
              }}
            >
              {showAuto && (
                <button
                  type="button"
                  onClick={() => { onChange('auto'); setIsOpen(false); }}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    border: 'none',
                    background: value === 'auto' ? 'rgba(37,99,235,0.06)' : 'transparent',
                    cursor: 'pointer',
                    fontSize: '13px',
                    color: 'var(--navy)',
                    fontFamily: 'var(--font-body)',
                    textAlign: 'left',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    transition: 'background 0.1s',
                    borderBottom: '1px solid var(--gray-100)',
                  }}
                >
                  <span style={{ fontSize: '16px' }}>🌐</span>
                  Détection automatique
                </button>
              )}
              {filtered.map((l) => (
                <button
                  key={l.code}
                  type="button"
                  onClick={() => { onChange(l.code); setIsOpen(false); }}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    border: 'none',
                    background: l.code === value ? 'rgba(37,99,235,0.06)' : 'transparent',
                    cursor: 'pointer',
                    fontSize: '13px',
                    color: l.code === value ? 'var(--blue)' : 'var(--navy)',
                    fontFamily: 'var(--font-body)',
                    fontWeight: l.code === value ? 600 : 400,
                    textAlign: 'left',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    transition: 'background 0.1s',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--gray-50)'; }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = l.code === value ? 'rgba(37,99,235,0.06)' : 'transparent';
                  }}
                >
                  <span style={{ fontSize: '16px' }}>{l.flag}</span>
                  {l.label}
                </button>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

function Select({
  value,
  onChange,
  label,
  options,
  exclude,
  showAuto,
}: {
  value: string;
  onChange: (v: string) => void;
  label: string;
  options: LanguageOption[];
  exclude?: string;
  showAuto?: boolean;
}) {
  return (
    <CustomSelect
      value={value}
      onChange={onChange}
      label={label}
      options={options}
      exclude={exclude}
      showAuto={showAuto}
    />
  );
}

export default function LanguageSelector({
  sourceLang,
  targetLang,
  onSourceChange,
  onTargetChange,
  onSwap,
  showSource = true,
}: LanguageSelectorProps) {
  const { t } = useTranslation();

  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: '10px' }}>
      {/* Source */}
      {showSource && (
        <div style={{ flex: 1 }}>
          <Select
            value={sourceLang}
            onChange={onSourceChange}
            label={t('story.source_lang')}
            options={sourceLanguages}
            exclude={targetLang}
            showAuto={true}
          />
        </div>
      )}

      {/* Swap button */}
      {showSource && (
        <motion.button
          whileHover={{ scale: 1.10 }}
          whileTap={{ scale: 0.90 }}
          onClick={onSwap}
          aria-label={t('story.swap_langs')}
          style={{
            width: '36px',
            height: '36px',
            borderRadius: '8px',
            border: '1.5px solid var(--gray-200)',
            background: 'var(--white)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--blue)',
            flexShrink: 0,
            marginBottom: '2px',
            transition: 'all 0.2s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = 'var(--blue)';
            e.currentTarget.style.boxShadow = '0 2px 8px rgba(37,99,235,0.15)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = 'var(--gray-200)';
            e.currentTarget.style.boxShadow = 'none';
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M7 16l-4-4 4-4" />
            <path d="M17 8l4 4-4 4" />
            <path d="M3 12h18" />
          </svg>
        </motion.button>
      )}

      {/* Target */}
      <div style={{ flex: 1 }}>
        <Select
          value={targetLang}
          onChange={onTargetChange}
          label={t('story.target_lang')}
          options={targetLanguages}
          exclude={showSource ? sourceLang : undefined}
        />
      </div>
    </div>
  );
}
