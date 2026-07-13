import { useState } from 'react';
import { useTranslation as useI18n } from 'react-i18next';
import { motion, AnimatePresence } from 'motion/react';
import { Check, ArrowRight, Zap, Target, ScanSearch, Loader2, Languages } from 'lucide-react';
import FileUploader from './FileUploader';
import LanguageSelector from './LanguageSelector';

export interface FormatOptions {
  mode: 'auto_fit' | 'preserve' | 'optimize' | 'adjust_margins' | 'compact';
  fontSizeScale: number;
  lineHeightScale: number;
  marginScale: number;
}

export interface TranslateConfig {
  file: File;
  targetLang: string;
  formatOptions: FormatOptions;
  quality: 'fast' | 'precise';
  pages: string;
  debug: boolean;
}

interface TranslationSectionProps {
  /** Démarre la traduction (le parent ouvre l'aperçu et gère le streaming). */
  onStartTranslate: (config: TranslateConfig) => void;
  isTranslating: boolean;
  onLibraryOpen?: () => void;
}

/** Le moteur v2 préserve TOUJOURS la mise en page d'origine : il n'y a plus de
 *  « mode de format » à choisir (l'ancien sélecteur n'avait qu'une option). */
const FORMAT_OPTIONS: FormatOptions = {
  mode: 'preserve',
  fontSizeScale: 1,
  lineHeightScale: 1,
  marginScale: 1,
};

export default function TranslationSection({ onStartTranslate, isTranslating, onLibraryOpen }: TranslationSectionProps) {
  const { t } = useI18n();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [sourceLang, setSourceLang] = useState('auto');
  const [targetLang, setTargetLang] = useState('en-US');
  const [quality, setQuality] = useState<'fast' | 'precise'>('fast');
  const [structureMode, setStructureMode] = useState(false);
  const [pages, setPages] = useState('');
  const [justReset, setJustReset] = useState(false);

  // Le concept de page n'existe proprement que pour PDF et PPTX (diapos).
  const ext = selectedFile?.name.split('.').pop()?.toLowerCase() ?? '';
  const supportsPageRange = ext === 'pdf' || ext === 'pptx';

  const handleFileSelect = (file: File | null) => {
    setSelectedFile(file);
    setPages(''); // une plage est propre à un document : on repart de zéro
    if (file) setJustReset(false);
  };

  const handleTranslate = () => {
    if (!selectedFile) return;
    onStartTranslate({
      file: selectedFile,
      targetLang,
      formatOptions: FORMAT_OPTIONS,
      quality,
      pages: supportsPageRange ? pages : '',
      debug: structureMode,
    });
  };

  const isReady = !!selectedFile && !isTranslating;

  const qualityModes = [
    {
      key: 'fast' as const,
      Icon: Zap,
      title: t('story.quality_fast', 'Rapide'),
      desc: t('story.quality_fast_desc', 'Quelques secondes par page'),
    },
    {
      key: 'precise' as const,
      Icon: Target,
      title: t('story.quality_precise', 'Précis'),
      desc: t('story.quality_precise_desc', 'Mises en page complexes · plus lent'),
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '18px', flex: 1, width: '560px', margin: '0 auto' }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '18px' }}>
        {/* Confirmation après un reset */}
        <AnimatePresence>
          {justReset && !selectedFile && (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              style={{
                padding: '10px 14px',
                borderRadius: '10px',
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
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '7px' }}>
                <Check size={15} strokeWidth={2.5} />
                {t('story.saved_to_library', 'Document sauvegardé dans votre bibliothèque.')}
              </span>
              {onLibraryOpen && (
                <button
                  onClick={onLibraryOpen}
                  style={{
                    background: 'none', border: 'none', color: '#16a34a',
                    cursor: 'pointer', fontSize: '12px', fontWeight: 600,
                    padding: 0, fontFamily: 'inherit', whiteSpace: 'nowrap',
                    display: 'inline-flex', alignItems: 'center', gap: '3px',
                  }}
                >
                  {t('library.view_action', 'Voir mes documents')}
                  <ArrowRight size={13} strokeWidth={2.5} />
                </button>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        <FileUploader selectedFile={selectedFile} onFileSelect={handleFileSelect} />

        <LanguageSelector
          sourceLang={sourceLang}
          targetLang={targetLang}
          onSourceChange={setSourceLang}
          onTargetChange={setTargetLang}
          onSwap={() => {
            if (sourceLang === 'auto') {
              setSourceLang('en-US');
              setTargetLang('auto');
            } else if (targetLang !== sourceLang) {
              setSourceLang(targetLang);
              setTargetLang(sourceLang);
            }
          }}
          showSource={true}
        />

        {/* Mode de traduction */}
        <div>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--gray-700)', marginBottom: '8px', letterSpacing: '0.01em' }}>
            {t('story.quality_label', 'Mode de traduction')}
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            {qualityModes.map(({ key, Icon, title, desc }) => {
              const active = quality === key;
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => setQuality(key)}
                  disabled={isTranslating}
                  style={{
                    textAlign: 'left',
                    padding: '12px 13px',
                    borderRadius: '12px',
                    border: active ? '1.5px solid var(--blue)' : '1px solid var(--gray-300)',
                    background: active ? 'rgba(37,99,235,0.05)' : 'var(--white)',
                    cursor: isTranslating ? 'not-allowed' : 'pointer',
                    fontFamily: 'inherit',
                    transition: 'all 0.15s ease',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                    boxShadow: active ? '0 1px 3px rgba(37,99,235,0.1)' : 'none',
                  }}
                >
                  <span style={{
                    display: 'inline-flex', alignItems: 'center', gap: '7px',
                    fontSize: '13px', fontWeight: 600,
                    color: active ? 'var(--blue)' : 'var(--gray-800)',
                  }}>
                    <Icon size={15} strokeWidth={2.2} />
                    {title}
                  </span>
                  <span style={{ fontSize: '11px', color: 'var(--gray-500)', lineHeight: 1.35 }}>
                    {desc}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Plage de pages (PDF / PPTX) */}
        <AnimatePresence>
          {selectedFile && supportsPageRange && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              style={{ overflow: 'hidden' }}
            >
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--gray-700)', marginBottom: '8px' }}>
                {ext === 'pptx'
                  ? t('story.pages_label_slides', 'Diapositives à traduire')
                  : t('story.pages_label', 'Pages à traduire')}
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
                  padding: '11px 13px',
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
              <span style={{ display: 'block', fontSize: '11px', color: 'var(--gray-500)', marginTop: '6px', lineHeight: 1.4 }}>
                {t('story.pages_hint', 'Laissez vide pour tout traduire. Les pages non sélectionnées restent dans leur langue d’origine.')}
              </span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Mode structure (diagnostic) — PDF uniquement, discret */}
        {ext === 'pdf' && (
          <button
            type="button"
            onClick={() => setStructureMode((v) => !v)}
            disabled={isTranslating}
            style={{
              width: '100%',
              textAlign: 'left',
              padding: '10px 12px',
              borderRadius: '10px',
              border: structureMode ? '1.5px solid var(--blue)' : '1px dashed var(--gray-300)',
              background: structureMode ? 'rgba(37,99,235,0.05)' : 'transparent',
              cursor: isTranslating ? 'not-allowed' : 'pointer',
              fontFamily: 'inherit',
              transition: 'all 0.15s ease',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
            }}
          >
            <span style={{
              width: '17px', height: '17px', borderRadius: '5px', flexShrink: 0,
              border: structureMode ? 'none' : '1px solid var(--gray-400)',
              background: structureMode ? 'var(--blue)' : 'transparent',
              color: 'var(--white)', display: 'flex', alignItems: 'center',
              justifyContent: 'center',
            }}>
              {structureMode && <Check size={12} strokeWidth={3} />}
            </span>
            <span style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: '6px',
                fontSize: '12px', fontWeight: 600,
                color: structureMode ? 'var(--blue)' : 'var(--gray-700)',
              }}>
                <ScanSearch size={14} strokeWidth={2.2} />
                {t('story.structure_label', 'Mode structure (sans traduction)')}
              </span>
              <span style={{ fontSize: '11px', color: 'var(--gray-500)', lineHeight: 1.35 }}>
                {t('story.structure_desc', 'Affiche les contours de blocs détectés — pour diagnostiquer la mise en page.')}
              </span>
            </span>
          </button>
        )}
      </div>

      {/* Action — la progression s'affiche désormais DANS l'aperçu, qui s'ouvre
          dès le démarrage et se remplit page par page. */}
      <div style={{ position: 'sticky', bottom: 0, background: 'inherit', paddingTop: '8px' }}>
        <motion.button
          whileHover={isReady ? { scale: 1.01 } : {}}
          whileTap={isReady ? { scale: 0.99 } : {}}
          onClick={handleTranslate}
          disabled={!isReady}
          style={{
            width: '100%',
            padding: '14px',
            borderRadius: '12px',
            border: 'none',
            background: isReady
              ? 'linear-gradient(135deg, var(--blue) 0%, #1d4ed8 100%)'
              : 'var(--gray-300)',
            color: 'white',
            fontWeight: 600,
            fontSize: '14px',
            cursor: isReady ? 'pointer' : 'not-allowed',
            transition: 'all 0.2s ease',
            boxShadow: isReady ? '0 4px 16px rgba(37,99,235,0.28)' : 'none',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '9px',
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
                <Loader2 size={16} strokeWidth={2.5} />
              </motion.span>
              {t('story.translating')}
            </>
          ) : (
            <>
              <Languages size={16} strokeWidth={2.2} />
              {t('story.btn_translate')}
            </>
          )}
        </motion.button>
      </div>
    </div>
  );
}
