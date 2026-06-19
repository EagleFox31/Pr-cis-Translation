import { useState } from 'react';
import { useTranslation as useI18n } from 'react-i18next';
import { useTranslationProgress } from '../../hooks/useTranslationProgress';
import { motion, AnimatePresence } from 'motion/react';
import FileUploader from './FileUploader';
import LanguageSelector from './LanguageSelector';
import FormatSelector from './FormatSelector';
import TranslationProgress from './TranslationProgress';
import type { FormatOption } from './FormatSelector';
import { showToast } from '../ui/Toast';

export interface FormatOptions {
  mode: 'auto_fit' | 'preserve' | 'optimize' | 'adjust_margins' | 'compact';
  fontSizeScale: number;
  lineHeightScale: number;
  marginScale: number;
}

interface TranslationSectionProps {
  onTranslationComplete?: (result: { blob: Blob; filename: string; file: File; targetLang: string }) => void;
  onLibraryOpen?: () => void;
}

function useFormatOptions(t: (key: string) => string): FormatOption[] {
  return [
    { key: 'preserve', label: t('story.mode_preserve'), desc: t('story.mode_preserve_desc'), icon: '📐' },
  ];
}

export default function TranslationSection({ onTranslationComplete, onLibraryOpen }: TranslationSectionProps) {
  const { t, i18n } = useI18n();
  const { translateFile, isTranslating, progress, error } = useTranslationProgress();
  const lang = i18n.language?.startsWith('fr') ? 'fr' : 'en';

  const formatOptions = useFormatOptions(t);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [sourceLang, setSourceLang] = useState('auto');
  const [targetLang, setTargetLang] = useState('en-US');
  const [formatMode, setFormatMode] = useState('preserve');
  const [quality, setQuality] = useState<'fast' | 'precise'>('fast');
  const [pages, setPages] = useState('');
  const [result, setResult] = useState<{ blob: Blob; filename: string } | null>(null);
  const [justReset, setJustReset] = useState(false);

  // Le concept de page n'existe proprement que pour PDF et PPTX (diapos).
  const ext = selectedFile?.name.split('.').pop()?.toLowerCase() ?? '';
  const supportsPageRange = ext === 'pdf' || ext === 'pptx';

  const handleFileSelect = (file: File | null) => {
    setSelectedFile(file);
    setPages(''); // une plage est propre à un document : on repart de zéro
    if (file) setJustReset(false);
  };

  const handleTranslate = async () => {
    if (!selectedFile) return;

    try {
      const formatOpts = {
        mode: formatMode as any,
        fontSizeScale: 1,
        lineHeightScale: 1,
        marginScale: 1,
      };
      const res = await translateFile(selectedFile, targetLang, formatOpts, quality, supportsPageRange ? pages : '');
      setResult(res);
      onTranslationComplete?.({ ...res, file: selectedFile, targetLang });
      showToast(
        'success',
        t('story.success_done'),
        res.filename,
        onLibraryOpen ? { label: t('library.view_action', 'Voir dans la bibliothèque'), onClick: onLibraryOpen } : undefined,
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : '';
      const isLarge = msg.includes('413') || msg.toLowerCase().includes('too large') || (!!selectedFile && selectedFile.size > 100 * 1024 * 1024);
      const isNetwork = msg.toLowerCase().includes('network') || msg.toLowerCase().includes('fetch') || msg.toLowerCase().includes('failed to fetch');
      const hint = isLarge
        ? (lang === 'fr' ? 'Essayez de compresser votre PDF avant de réessayer.' : 'Try compressing your PDF before retrying.')
        : isNetwork
          ? (lang === 'fr' ? 'Vérifiez votre connexion internet et réessayez.' : 'Check your internet connection and try again.')
          : (msg || t('story.error_default'));
      showToast('error', t('story.error_default'), hint);
    }
  };

  const handleReset = () => {
    setSelectedFile(null);
    setPages('');
    setResult(null);
    setJustReset(true);
  };

  const isReady = !!selectedFile && !isTranslating;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', flex: 1, width: '560px', margin: '0 auto' }}>
      {/* Form inputs */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Empty state after reset */}
        <AnimatePresence>
          {justReset && !selectedFile && (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              style={{
                padding: '10px 14px',
                borderRadius: '8px',
                background: '#f0fdf4',
                border: '1px solid #86efac',
                color: '#166534',
                fontSize: '13px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '8px',
              }}
            >
              <span>✓ {t('story.saved_to_library', 'Document sauvegardé dans votre bibliothèque.')}</span>
              {onLibraryOpen && (
                <button
                  onClick={onLibraryOpen}
                  style={{
                    background: 'none', border: 'none', color: '#16a34a',
                    cursor: 'pointer', fontSize: '12px', fontWeight: 600,
                    padding: 0, fontFamily: 'inherit', whiteSpace: 'nowrap',
                    textDecoration: 'underline',
                  }}
                >
                  {t('library.view_action', 'Voir mes documents')} →
                </button>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* File Upload */}
        <FileUploader selectedFile={selectedFile} onFileSelect={handleFileSelect} />

        {/* Language Selection */}
        <LanguageSelector
          sourceLang={sourceLang}
          targetLang={targetLang}
          onSourceChange={setSourceLang}
          onTargetChange={setTargetLang}
          onSwap={() => {
            if (sourceLang === 'auto') {
              setSourceLang('en-US');
              setTargetLang('auto');
            } else if (targetLang === sourceLang) {
              // No-op if same
            } else {
              setSourceLang(targetLang);
              setTargetLang(sourceLang);
            }
          }}
          showSource={true}
        />

        {/* Format Options */}
        <FormatSelector
          options={formatOptions}
          current={formatMode}
          onChange={setFormatMode}
        />

        {/* Translation quality mode */}
        <div>
          <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: 'var(--gray-700)', marginBottom: '8px' }}>
            {t('story.quality_label', 'Mode de traduction')}
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            {([
              { key: 'fast', icon: '⚡', title: t('story.quality_fast', 'Rapide'), desc: t('story.quality_fast_desc', 'Quelques secondes · version stable') },
              { key: 'precise', icon: '🎯', title: t('story.quality_precise', 'Précis'), desc: t('story.quality_precise_desc', 'Raisonnement · mises en page complexes · plus lent') },
            ] as const).map((opt) => {
              const active = quality === opt.key;
              return (
                <button
                  key={opt.key}
                  type="button"
                  onClick={() => setQuality(opt.key)}
                  disabled={isTranslating}
                  style={{
                    textAlign: 'left',
                    padding: '10px 12px',
                    borderRadius: '10px',
                    border: active ? '2px solid var(--blue)' : '1px solid var(--gray-300)',
                    background: active ? 'rgba(37,99,235,0.06)' : 'var(--white)',
                    cursor: isTranslating ? 'not-allowed' : 'pointer',
                    fontFamily: 'inherit',
                    transition: 'all 0.15s ease',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '2px',
                  }}
                >
                  <span style={{ fontSize: '13px', fontWeight: 600, color: active ? 'var(--blue)' : 'var(--gray-800)' }}>
                    {opt.icon} {opt.title}
                  </span>
                  <span style={{ fontSize: '11px', color: 'var(--gray-500)', lineHeight: 1.3 }}>
                    {opt.desc}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Page range — only when a PDF/PPTX is loaded */}
        <AnimatePresence>
          {selectedFile && supportsPageRange && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              style={{ overflow: 'hidden' }}
            >
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: 'var(--gray-700)', marginBottom: '8px' }}>
                {t('story.pages_label', ext === 'pptx' ? 'Diapositives à traduire' : 'Pages à traduire')}
              </label>
              <input
                type="text"
                inputMode="numeric"
                value={pages}
                onChange={(e) => setPages(e.target.value.replace(/[^0-9,\-\s]/g, ''))}
                disabled={isTranslating}
                placeholder={t('story.pages_placeholder', 'Ex. 1-5, 8, 11-13 — vide = tout le document')}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: '10px',
                  border: '1px solid var(--gray-300)',
                  background: 'var(--white)',
                  fontSize: '13px',
                  fontFamily: 'inherit',
                  color: 'var(--gray-800)',
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
              />
              <span style={{ display: 'block', fontSize: '11px', color: 'var(--gray-500)', marginTop: '6px', lineHeight: 1.3 }}>
                {t('story.pages_hint', 'Laissez vide pour traduire tout le document. Les pages non sélectionnées restent dans leur langue d’origine.')}
              </span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Bottom actions — pinned */}
      <div style={{ position: 'sticky', bottom: 0, background: 'inherit', paddingTop: '8px' }}>

        {/* Progression temps réel */}
        <AnimatePresence>
          {isTranslating && (
            <div style={{ marginBottom: '12px' }}>
              <TranslationProgress progress={progress} lang={lang} />
            </div>
          )}
        </AnimatePresence>

        {/* Translate Button */}
        <motion.button
        whileHover={isReady ? { scale: 1.01 } : {}}
        whileTap={isReady ? { scale: 0.99 } : {}}
        onClick={handleTranslate}
        disabled={!isReady}
        style={{
          width: '100%',
          padding: '13px',
          borderRadius: '10px',
          border: 'none',
          background: isReady
            ? 'linear-gradient(135deg, var(--blue) 0%, #1d4ed8 100%)'
            : 'var(--gray-300)',
          color: 'white',
          fontWeight: 600,
          fontSize: '14px',
          cursor: isReady ? 'pointer' : 'not-allowed',
          transition: 'all 0.2s ease',
          boxShadow: isReady ? '0 4px 16px rgba(37,99,235,0.3)' : 'none',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '8px',
          fontFamily: 'inherit',
        }}
      >
        {isTranslating ? (
          <>
            <motion.span
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
              style={{ display: 'inline-flex' }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <circle cx="12" cy="12" r="10" opacity="0.25" />
                <path d="M12 2a10 10 0 0 1 10 10" strokeLinecap="round" />
              </svg>
            </motion.span>
            {t('story.translating')}
          </>
        ) : (
          <>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 8l6 6" /><path d="M11 8v8" /><path d="M4 16h8" /><path d="M13 8h3a3 3 0 0 1 3 3v0a3 3 0 0 1-3 3h-3" />
            </svg>
            {t('story.btn_translate')}
          </>
        )}
      </motion.button>

      {error && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          style={{
            padding: '10px 14px',
            borderRadius: '8px',
            background: '#fef2f2',
            border: '1px solid #fecaca',
            color: '#dc2626',
            fontSize: '13px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <span>⚠</span> {error}
        </motion.div>
      )}

      {/* Result Actions */}
      {result && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          style={{
            display: 'flex',
            gap: '8px',
            marginTop: '4px',
          }}
        >
          <button
            onClick={() => {
              if (result.blob) {
                const url = URL.createObjectURL(result.blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = result.filename;
                document.body.appendChild(a);
                a.click();
                URL.revokeObjectURL(url);
                document.body.removeChild(a);
              }
            }}
            style={{
              flex: 1,
              padding: '10px',
              borderRadius: '8px',
              border: 'none',
              background: 'var(--blue)',
              color: 'white',
              fontWeight: 600,
              fontSize: '13px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              fontFamily: 'inherit',
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 5v14" /><path d="M19 12l-7 7-7-7" />
            </svg>
            {t('story.download')}
          </button>
          <button
            onClick={handleReset}
            style={{
              padding: '10px 16px',
              borderRadius: '8px',
              border: '1px solid var(--gray-300)',
              background: 'var(--white)',
              color: 'var(--gray-700)',
              fontWeight: 500,
              fontSize: '13px',
              cursor: 'pointer',
              fontFamily: 'inherit',
              transition: 'all 0.15s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = '#f8fafc'; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'white'; }}
          >
            {t('story.new_translation')}
          </button>
        </motion.div>
      )}
      </div>
    </div>
  );
}
