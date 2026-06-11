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
  { code: 'fr', label: 'Français', flag: '🇫🇷' },
  { code: 'en', label: 'English', flag: '🇬🇧' },
  { code: 'es', label: 'Español', flag: '🇪🇸' },
  { code: 'de', label: 'Deutsch', flag: '🇩🇪' },
  { code: 'it', label: 'Italiano', flag: '🇮🇹' },
  { code: 'pt', label: 'Português', flag: '🇵🇹' },
  { code: 'ar', label: 'العربية', flag: '🇸🇦' },
  { code: 'zh', label: '中文', flag: '🇨🇳' },
  { code: 'ja', label: '日本語', flag: '🇯🇵' },
  { code: 'ko', label: '한국어', flag: '🇰🇷' },
  { code: 'ru', label: 'Русский', flag: '🇷🇺' },
  { code: 'nl', label: 'Nederlands', flag: '🇳🇱' },
];

function Select({
  value,
  onChange,
  label,
  options,
  exclude,
}: {
  value: string;
  onChange: (v: string) => void;
  label: string;
  options: LanguageOption[];
  exclude?: string;
}) {
  return (
    <div>
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
        {label}
      </label>
      <div style={{ position: 'relative' }}>
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          style={{
            width: '100%',
            padding: '10px 14px',
            borderRadius: '10px',
            border: '1px solid var(--gray-300)',
            fontSize: '13px',
            fontWeight: 500,
            appearance: 'none',
            backgroundColor: '#f8fafc',
            color: 'var(--navy)',
            cursor: 'pointer',
            outline: 'none',
            fontFamily: 'inherit',
            transition: 'border-color 0.2s',
          }}
          onFocus={(e) => { e.target.style.borderColor = 'var(--blue)'; }}
          onBlur={(e) => { e.target.style.borderColor = 'var(--gray-300)'; }}
        >
          {options
            .filter((l) => l.code !== exclude)
            .map((l) => (
              <option key={l.code} value={l.code}>
                {l.flag} {l.label}
              </option>
            ))}
        </select>
        <div
          style={{
            position: 'absolute',
            right: '12px',
            top: '50%',
            transform: 'translateY(-50%)',
            pointerEvents: 'none',
            color: '#94a3b8',
          }}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </div>
      </div>
    </div>
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
  return (
    <div style={{ display: 'grid', gridTemplateColumns: showSource ? '1fr auto 1fr' : '1fr', gap: '10px', alignItems: 'end' }}>
      {showSource && (
        <Select
          value={sourceLang}
          onChange={onSourceChange}
          label="Langue source"
          options={languages}
          exclude={targetLang}
        />
      )}

      {showSource && (
        <button
          onClick={onSwap}
          style={{
            width: '34px',
            height: '34px',
            borderRadius: '50%',
            border: '1px solid var(--gray-300)',
            background: 'var(--white)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--blue)',
            transition: 'all 0.2s',
            marginBottom: '2px',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = '#eff6ff'; e.currentTarget.style.borderColor = 'var(--blue)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'white'; e.currentTarget.style.borderColor = 'var(--gray-300)'; }}
          aria-label="Inverser les langues"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M7 16l-4-4 4-4" />
            <path d="M17 8l4 4-4 4" />
            <path d="M3 12h18" />
          </svg>
        </button>
      )}

      <Select
        value={targetLang}
        onChange={onTargetChange}
        label="Langue cible"
        options={languages}
        exclude={showSource ? sourceLang : undefined}
      />
    </div>
  );
}
