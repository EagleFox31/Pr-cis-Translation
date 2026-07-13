import { useState, useRef, useEffect, useMemo, useId } from 'react';
import { useTranslation } from 'react-i18next';
import { motion, AnimatePresence } from 'motion/react';
import { ChevronDown, Search, Check, Ban } from 'lucide-react';
import { LANGUAGES, isLangAvailable, findLang } from '../../lib/languages';
import type { Language } from '../../lib/languages';

interface LanguagePickerProps {
  value: string;
  onChange: (code: string) => void;
  /** Extension du document : conditionne les langues rendables. */
  ext: string;
  disabled?: boolean;
}

/** Puce du code langue — remplace les drapeaux emoji, qui ne sont pas rendus
 *  sous Windows (« 🇺🇸 » s'y affiche littéralement « US ») et qui associent à
 *  tort une langue à un pays. */
function CodeChip({ code, active }: { code: string; active?: boolean }) {
  return (
    <span
      aria-hidden="true"
      style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        minWidth: '26px', height: '20px', padding: '0 5px', flexShrink: 0,
        borderRadius: '5px',
        background: active ? 'var(--blue)' : 'var(--gray-100)',
        color: active ? 'var(--white)' : 'var(--gray-600)',
        fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 700,
        letterSpacing: '0.04em', textTransform: 'uppercase',
        transition: 'background 0.15s, color 0.15s',
      }}
    >
      {code}
    </span>
  );
}

export default function LanguagePicker({ value, onChange, ext, disabled }: LanguagePickerProps) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [cursor, setCursor] = useState(0);

  const ref = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const listboxId = useId();

  const selected = findLang(value);

  // Les langues non rendables dans ce format restent VISIBLES mais désactivées :
  // l'utilisateur comprend pourquoi le choix est indisponible plutôt que de
  // chercher une langue qui aurait silencieusement disparu de la liste.
  const options = useMemo(() => {
    const q = query.trim().toLowerCase();
    const match = (l: Language) =>
      !q || l.label.toLowerCase().includes(q) || l.code.includes(q);
    return LANGUAGES.filter(match).map((l) => ({
      lang: l,
      available: isLangAvailable(l, ext),
    }));
  }, [query, ext]);

  const selectableIdx = options
    .map((o, i) => (o.available ? i : -1))
    .filter((i) => i >= 0);

  useEffect(() => {
    if (!isOpen) return;
    const onClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setIsOpen(false);
    };
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, [isOpen]);

  // À l'ouverture : focus sur la recherche, curseur sur l'option courante.
  useEffect(() => {
    if (isOpen) {
      searchRef.current?.focus();
      const i = options.findIndex((o) => o.lang.code === value);
      setCursor(i >= 0 ? i : (selectableIdx[0] ?? 0));
    } else {
      setQuery('');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  const commit = (i: number) => {
    const opt = options[i];
    if (!opt || !opt.available) return;
    onChange(opt.lang.code);
    setIsOpen(false);
  };

  const moveCursor = (dir: 1 | -1) => {
    if (!selectableIdx.length) return;
    const pos = selectableIdx.indexOf(cursor);
    const next = pos === -1
      ? selectableIdx[0]
      : selectableIdx[(pos + dir + selectableIdx.length) % selectableIdx.length];
    setCursor(next);
    listRef.current
      ?.querySelector<HTMLElement>(`[data-idx="${next}"]`)
      ?.scrollIntoView({ block: 'nearest' });
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); moveCursor(1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); moveCursor(-1); }
    else if (e.key === 'Enter') { e.preventDefault(); commit(cursor); }
    else if (e.key === 'Escape') { e.preventDefault(); setIsOpen(false); }
  };

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        type="button"
        onClick={() => !disabled && setIsOpen((v) => !v)}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={isOpen ? listboxId : undefined}
        style={{
          width: '100%',
          padding: '11px 12px',
          borderRadius: '10px',
          border: isOpen ? '1.5px solid var(--blue)' : '1.5px solid var(--gray-200)',
          background: disabled ? 'var(--gray-50)' : 'var(--white)',
          color: 'var(--navy)',
          fontSize: '14px',
          fontWeight: 500,
          fontFamily: 'inherit',
          textAlign: 'left',
          cursor: disabled ? 'not-allowed' : 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: '9px',
          outline: 'none',
          boxShadow: isOpen ? '0 0 0 3px rgba(37,99,235,0.10)' : 'none',
          transition: 'border-color 0.15s, box-shadow 0.15s',
        }}
      >
        <CodeChip code={selected?.code ?? '—'} active />
        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {selected?.label ?? t('story.target_lang')}
        </span>
        <motion.span
          animate={{ rotate: isOpen ? 180 : 0 }}
          transition={{ duration: 0.18 }}
          style={{ display: 'inline-flex', color: 'var(--gray-400)', flexShrink: 0 }}
        >
          <ChevronDown size={16} strokeWidth={2.2} />
        </motion.span>
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 5, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.15, ease: 'easeOut' }}
            onKeyDown={onKeyDown}
            style={{
              position: 'absolute',
              top: '100%', left: 0, right: 0,
              zIndex: 200,
              background: 'var(--white)',
              border: '1px solid var(--gray-200)',
              borderRadius: '12px',
              boxShadow: '0 16px 40px rgba(13,27,62,0.14)',
              overflow: 'hidden',
            }}
          >
            {/* Recherche */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: '8px',
              padding: '10px 12px', borderBottom: '1px solid var(--gray-100)',
            }}>
              <Search size={14} strokeWidth={2.2} style={{ color: 'var(--gray-400)', flexShrink: 0 }} />
              <input
                ref={searchRef}
                type="text"
                value={query}
                onChange={(e) => { setQuery(e.target.value); setCursor(0); }}
                placeholder={t('story.lang_search', 'Rechercher une langue…')}
                aria-label={t('story.lang_search', 'Rechercher une langue…')}
                style={{
                  flex: 1, border: 'none', outline: 'none', background: 'transparent',
                  fontSize: '13px', fontFamily: 'inherit', color: 'var(--navy)',
                }}
              />
            </div>

            <div
              ref={listRef}
              id={listboxId}
              role="listbox"
              style={{ maxHeight: '244px', overflowY: 'auto', padding: '4px' }}
            >
              {options.length === 0 && (
                <p style={{ padding: '18px 12px', textAlign: 'center', fontSize: '13px', color: 'var(--gray-500)' }}>
                  {t('story.lang_none', 'Aucune langue trouvée')}
                </p>
              )}

              {options.map(({ lang, available }, i) => {
                const isSel = lang.code === value;
                const isCur = i === cursor;
                return (
                  <button
                    key={lang.code}
                    data-idx={i}
                    type="button"
                    role="option"
                    aria-selected={isSel}
                    aria-disabled={!available}
                    disabled={!available}
                    onClick={() => commit(i)}
                    onMouseEnter={() => available && setCursor(i)}
                    title={available ? undefined : t('story.lang_pdf_unsupported', 'Écriture non rendable en PDF : les polices du document ne contiennent pas ces caractères.')}
                    style={{
                      width: '100%',
                      display: 'flex', alignItems: 'center', gap: '9px',
                      padding: '9px 10px',
                      border: 'none',
                      borderRadius: '8px',
                      background: !available ? 'transparent' : isCur ? 'var(--gray-50)' : 'transparent',
                      cursor: available ? 'pointer' : 'not-allowed',
                      opacity: available ? 1 : 0.45,
                      fontFamily: 'inherit',
                      fontSize: '13.5px',
                      fontWeight: isSel ? 600 : 400,
                      color: isSel ? 'var(--blue)' : 'var(--navy)',
                      textAlign: 'left',
                      transition: 'background 0.1s',
                    }}
                  >
                    <CodeChip code={lang.code} active={isSel} />
                    <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {lang.label}
                    </span>
                    {!available && <Ban size={13} strokeWidth={2.2} style={{ color: 'var(--gray-400)', flexShrink: 0 }} />}
                    {isSel && available && <Check size={14} strokeWidth={2.8} style={{ flexShrink: 0 }} />}
                  </button>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
