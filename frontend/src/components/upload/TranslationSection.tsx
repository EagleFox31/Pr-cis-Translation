import { useState } from 'react';
import { useTranslation as useI18n } from 'react-i18next';
import { useTranslation } from '../../hooks/useTranslation';
import { motion } from 'motion/react';
import FileUploader from './FileUploader';
import LanguageSelector from './LanguageSelector';
import FormatSelector from './FormatSelector';
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
}

function useFormatOptions(t: (key: string) => string): FormatOption[] {
  return [
    { key: 'preserve', label: t('story.mode_preserve'), desc: t('story.mode_preserve_desc'), icon: '📐' },
  ];
}

export default function TranslationSection({ onTranslationComplete }: TranslationSectionProps) {
  const { t } = useI18n();
  const { translateFile, isTranslating, error } = useTranslation();

  const formatOptions = useFormatOptions(t);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [sourceLang, setSourceLang] = useState('auto');
  const [targetLang, setTargetLang] = useState('en-US');
  const [formatMode, setFormatMode] = useState('preserve');
  const [result, setResult] = useState<{ blob: Blob; filename: string } | null>(null);

  const handleTranslate = async () => {
    if (!selectedFile) return;

    try {
      const formatOpts = {
        mode: formatMode as any,
        fontSizeScale: 1,
        lineHeightScale: 1,
        marginScale: 1,
      };
      const res = await translateFile(selectedFile, targetLang, formatOpts);
      setResult(res);
      onTranslationComplete?.({ ...res, file: selectedFile, targetLang });
      showToast('success', t('story.success_done'), `${res.filename}`);
    } catch (err) {
      showToast('error', 'Erreur de traduction', err instanceof Error ? err.message : t('story.error_default'));
    }
  };

  const handleReset = () => {
    setSelectedFile(null);
    setResult(null);
  };

  const isReady = !!selectedFile && !isTranslating;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', flex: 1, width: '560px', margin: '0 auto' }}>
      {/* Form inputs */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* File Upload */}
        <FileUploader selectedFile={selectedFile} onFileSelect={setSelectedFile} />

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
      </div>

      {/* Bottom actions — pinned */}
      <div style={{ position: 'sticky', bottom: 0, background: 'inherit', paddingTop: '8px' }}>
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
