import { useState, useEffect } from 'react';
import { useTranslation as useI18n } from 'react-i18next';
import { motion, AnimatePresence } from 'motion/react';
import {
  Check, ArrowRight, Loader2, Languages, Wand2, FileText,
  SlidersHorizontal, ChevronDown, ScanSearch, Info,
} from 'lucide-react';
import FileUploader from './FileUploader';
import LanguagePicker from './LanguagePicker';
import { useAuth } from '../../contexts/AuthContext';
import { findLang, isLangAvailable } from '../../lib/languages';

export interface TranslateConfig {
  file: File;
  targetLang: string;
  /** Plage de pages ('1-5, 8'), vide = tout le document. PDF uniquement. */
  pages: string;
  /** Mode structure : rend les contours de blocs sans traduire (diagnostic). */
  debug: boolean;
  /** Mode précis : utilise le modèle de raisonnement (admin uniquement). */
  precise: boolean;
}

interface TranslationSectionProps {
  /** Démarre la traduction (le parent ouvre l'aperçu et gère le streaming). */
  onStartTranslate: (config: TranslateConfig) => void;
  isTranslating: boolean;
  onLibraryOpen?: () => void;
}

const LABEL_STYLE: React.CSSProperties = {
  display: 'block',
  fontSize: '12px',
  fontWeight: 600,
  color: 'var(--gray-700)',
  marginBottom: '7px',
};

/** Puce d'étape numérotée — donne au formulaire une progression lisible. */
function StepBadge({ n, done }: { n: number; done?: boolean }) {
  return (
    <span
      aria-hidden="true"
      style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        width: '19px', height: '19px', borderRadius: '50%', flexShrink: 0,
        background: done ? 'var(--blue)' : 'var(--gray-200)',
        color: done ? 'var(--white)' : 'var(--gray-600)',
        fontSize: '10.5px', fontWeight: 700,
        transition: 'background 0.2s, color 0.2s',
      }}
    >
      {done ? <Check size={11} strokeWidth={3.2} /> : n}
    </span>
  );
}

export default function TranslationSection({
  onStartTranslate, isTranslating, onLibraryOpen,
}: TranslationSectionProps) {
  const { t } = useI18n();

  const [file, setFile] = useState<File | null>(null);
  const [targetLang, setTargetLang] = useState('en-US');
  const [pages, setPages] = useState('');
  const [structureMode, setStructureMode] = useState(false);
  const { user } = useAuth();
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [preciseMode, setPreciseMode] = useState(false);
  const [justReset, setJustReset] = useState(false);

  const ext = file?.name.split('.').pop()?.toLowerCase() ?? '';
  const isPdf = ext === 'pdf';

  // Une langue rendable en DOCX peut ne pas l'être en PDF (CJK, arabe : aucune
  // police du document ne porte ces glyphes). Si le document choisi rend la
  // cible courante impossible, on retombe sur l'anglais plutôt que de lancer
  // une traduction qui produirait des pages vides.
  useEffect(() => {
    const lang = findLang(targetLang);
    if (file && lang && !isLangAvailable(lang, ext)) setTargetLang('en-US');
  }, [file, ext, targetLang]);

  const handleFile = (f: File | null) => {
    setFile(f);
    setPages('');          // une plage est propre à un document
    if (f) setJustReset(false);
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || isTranslating) return;
    onStartTranslate({
      file,
      targetLang,
      pages: isPdf ? pages.trim() : '',
      debug: isPdf && structureMode,
      precise: isPdf && preciseMode,
    });
  };

  const ready = !!file && !isTranslating;
  const isAdmin = user?.plan === 'admin';
  const advancedCount = (pages.trim() ? 1 : 0) + (structureMode ? 1 : 0) + (preciseMode ? 1 : 0);

  return (
    <form
      onSubmit={submit}
      style={{ display: 'flex', flexDirection: 'column', gap: '18px', flex: 1, width: '100%' }}
    >
      {/* En-tête — ancre le formulaire : le titre reste fixe quel que soit
          l'état, et annonce ce que fait la carte. */}
      <header style={{
        display: 'flex', alignItems: 'center', gap: '11px',
        paddingBottom: '16px', borderBottom: '1px solid var(--gray-100)',
      }}>
        <span style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          width: '36px', height: '36px', borderRadius: '10px', flexShrink: 0,
          background: 'var(--blue-light)', color: 'var(--blue)',
        }}>
          <FileText size={18} strokeWidth={2} />
        </span>
        <div style={{ minWidth: 0 }}>
          <h3 style={{
            margin: 0, fontSize: '15px', fontWeight: 700,
            color: 'var(--navy)', lineHeight: 1.3,
          }}>
            {t('story.form_title')}
          </h3>
          <p style={{ margin: '2px 0 0', fontSize: '12px', color: 'var(--gray-500)', lineHeight: 1.4 }}>
            {t('story.form_subtitle')}
          </p>
        </div>
      </header>

      {/* Visiteur non connecté → invitation à créer un compte */}
      {!user && (
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
          justifyContent: 'center', textAlign: 'center', gap: '16px', padding: '20px 0',
        }}>
          <div style={{
            width: '48px', height: '48px', borderRadius: '12px',
            background: 'var(--blue-light)', color: 'var(--blue)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Languages size={22} strokeWidth={2} />
          </div>
          <div>
            <h4 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--gray-900)', margin: '0 0 4px' }}>
              Connectez-vous pour débloquer l'offre Freemium
            </h4>
          </div>
          <div style={{ display: 'flex', gap: '10px', marginTop: '4px' }}>
            <a href="/login" onClick={(e) => { e.preventDefault(); window.location.href = '/login'; }}
              style={{
                padding: '10px 22px', borderRadius: '10px',
                background: 'var(--blue)', color: 'white', fontWeight: 600,
                fontSize: '14px', textDecoration: 'none', fontFamily: 'inherit',
              }}>
              Se connecter
            </a>
            <a href="/register" onClick={(e) => { e.preventDefault(); window.location.href = '/register'; }}
              style={{
                padding: '10px 22px', borderRadius: '10px',
                border: '1.5px solid var(--gray-200)', background: 'white',
                color: 'var(--gray-700)', fontWeight: 600,
                fontSize: '14px', textDecoration: 'none', fontFamily: 'inherit',
              }}>
              S'inscrire
            </a>
          </div>
        </div>
      )}

      {user ? (
      <><div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '18px' }}>
        {/* Confirmation après sauvegarde en bibliothèque */}
        <AnimatePresence>
          {justReset && !file && (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px',
                padding: '10px 14px', borderRadius: '10px',
                background: '#f0fdf4', border: '1px solid #86efac',
                color: '#166534', fontSize: '13px',
              }}
            >
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '7px' }}>
                <Check size={15} strokeWidth={2.5} />
                {t('story.saved_to_library')}
              </span>
              {onLibraryOpen && (
                <button
                  type="button"
                  onClick={onLibraryOpen}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: '3px',
                    background: 'none', border: 'none', color: '#16a34a',
                    cursor: 'pointer', fontSize: '12px', fontWeight: 600,
                    padding: 0, fontFamily: 'inherit', whiteSpace: 'nowrap',
                  }}
                >
                  {t('library.view_action')}
                  <ArrowRight size={13} strokeWidth={2.5} />
                </button>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Étape 1 — Document */}
        <div>
          <span style={{ ...LABEL_STYLE, display: 'flex', alignItems: 'center', gap: '7px' }}>
            <StepBadge n={1} done={!!file} />
            {t('story.step_document', 'Votre document')}
          </span>
          <FileUploader selectedFile={file} onFileSelect={handleFile} disabled={isTranslating} />
        </div>

        {/* Étape 2 — Langue cible. La source est détectée par le modèle : aucun
            choix à faire, donc aucun champ à afficher. */}
        <div>
          <label htmlFor="target-lang" style={{ ...LABEL_STYLE, display: 'flex', alignItems: 'center', gap: '7px' }}>
            <StepBadge n={2} done={!!file} />
            {t('story.step_target', 'Traduire vers')}
          </label>
          <div id="target-lang">
            <LanguagePicker
              value={targetLang}
              onChange={setTargetLang}
              ext={ext}
              disabled={isTranslating}
            />
          </div>
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: '5px',
            marginTop: '7px', fontSize: '11.5px', color: 'var(--gray-500)',
          }}>
            <Wand2 size={12} strokeWidth={2} style={{ flexShrink: 0 }} />
            {t('story.source_auto', 'La langue du document est détectée automatiquement.')}
          </span>
        </div>

        {/* Options avancées — repliées : elles ne concernent que le PDF et ne
            servent qu'à des cas particuliers (extrait, diagnostic). */}
        <AnimatePresence>
          {isPdf && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              style={{ overflow: 'hidden' }}
            >
              <button
                type="button"
                onClick={() => setShowAdvanced((v) => !v)}
                aria-expanded={showAdvanced}
                style={{
                  width: '100%', display: 'flex', alignItems: 'center', gap: '8px',
                  padding: '9px 2px', background: 'none', border: 'none',
                  cursor: 'pointer', fontFamily: 'inherit',
                  fontSize: '12px', fontWeight: 600, color: 'var(--gray-600)',
                }}
              >
                <SlidersHorizontal size={13} strokeWidth={2.2} />
                {t('story.advanced', 'Options avancées')}
                {advancedCount > 0 && (
                  <span style={{
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    minWidth: '16px', height: '16px', padding: '0 4px', borderRadius: '999px',
                    background: 'var(--blue-light)', color: 'var(--blue)',
                    fontSize: '10px', fontWeight: 700,
                  }}>
                    {advancedCount}
                  </span>
                )}
                <span style={{ flex: 1 }} />
                <motion.span
                  animate={{ rotate: showAdvanced ? 180 : 0 }}
                  transition={{ duration: 0.18 }}
                  style={{ display: 'inline-flex', color: 'var(--gray-400)' }}
                >
                  <ChevronDown size={15} strokeWidth={2.2} />
                </motion.span>
              </button>

              <AnimatePresence>
                {showAdvanced && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.22, ease: [0.4, 0, 0.2, 1] }}
                    style={{ overflow: 'hidden' }}
                  >
                    <div style={{
                      display: 'flex', flexDirection: 'column', gap: '16px',
                      padding: '14px', marginTop: '2px',
                      borderRadius: '12px', border: '1px solid var(--gray-200)',
                      background: 'var(--gray-50)',
                    }}>
                      {/* Plage de pages */}
                      <div>
                        <label htmlFor="pages" style={LABEL_STYLE}>
                          {t('story.pages_label')}
                        </label>
                        <input
                          id="pages"
                          type="text"
                          inputMode="numeric"
                          value={pages}
                          onChange={(e) => setPages(e.target.value.replace(/[^0-9,\-\s]/g, ''))}
                          disabled={isTranslating}
                          placeholder={t('story.pages_placeholder')}
                          aria-describedby="pages-hint"
                          style={{
                            width: '100%', boxSizing: 'border-box',
                            padding: '10px 12px', borderRadius: '9px',
                            border: '1px solid var(--gray-300)', background: 'var(--white)',
                            fontSize: '13px', fontFamily: 'inherit', color: 'var(--gray-800)',
                            outline: 'none',
                          }}
                        />
                        <span id="pages-hint" style={{
                          display: 'block', marginTop: '6px',
                          fontSize: '11px', color: 'var(--gray-500)', lineHeight: 1.45,
                        }}>
                          {t('story.pages_hint')}
                        </span>
                      </div>

                      {/* Mode précis (admin) */}
                      {isAdmin && (
                        <label
                          htmlFor="precise"
                          style={{
                            display: 'flex', alignItems: 'flex-start', gap: '10px',
                            cursor: isTranslating ? 'not-allowed' : 'pointer',
                            padding: '12px', borderRadius: '10px',
                            background: preciseMode ? '#fef9c3' : 'transparent',
                            border: preciseMode ? '1px solid #facc15' : '1px solid transparent',
                            transition: 'all 0.2s',
                          }}
                        >
                          <input
                            id="precise"
                            type="checkbox"
                            checked={preciseMode}
                            onChange={(e) => setPreciseMode(e.target.checked)}
                            disabled={isTranslating}
                            style={{
                              width: '16px', height: '16px', marginTop: '1px',
                              accentColor: '#ca8a04', flexShrink: 0, cursor: 'inherit',
                            }}
                          />
                          <span style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                            <span style={{
                              display: 'inline-flex', alignItems: 'center', gap: '6px',
                              fontSize: '12.5px', fontWeight: 600,
                              color: preciseMode ? '#854d0e' : 'var(--gray-800)',
                            }}>
                              <Wand2 size={13} strokeWidth={2.2} />
                              Mode précis (admin)
                            </span>
                            <span style={{ fontSize: '11px', color: 'var(--gray-500)', lineHeight: 1.45 }}>
                              Utilise le modèle de raisonnement — plus lent (~2 min/page) mais plus fiable sur les mises en page complexes.
                            </span>
                          </span>
                        </label>
                      )}

                      {/* Mode structure (diagnostic) */}
                      <label
                        htmlFor="structure"
                        style={{
                          display: 'flex', alignItems: 'flex-start', gap: '10px',
                          cursor: isTranslating ? 'not-allowed' : 'pointer',
                        }}
                      >
                        <input
                          id="structure"
                          type="checkbox"
                          checked={structureMode}
                          onChange={(e) => setStructureMode(e.target.checked)}
                          disabled={isTranslating}
                          style={{
                            width: '16px', height: '16px', marginTop: '1px',
                            accentColor: 'var(--blue)', flexShrink: 0, cursor: 'inherit',
                          }}
                        />
                        <span style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                          <span style={{
                            display: 'inline-flex', alignItems: 'center', gap: '6px',
                            fontSize: '12.5px', fontWeight: 600, color: 'var(--gray-800)',
                          }}>
                            <ScanSearch size={13} strokeWidth={2.2} />
                            {t('story.structure_label')}
                          </span>
                          <span style={{ fontSize: '11px', color: 'var(--gray-500)', lineHeight: 1.45 }}>
                            {t('story.structure_desc')}
                          </span>
                        </span>
                      </label>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Action */}
      <div style={{ position: 'sticky', bottom: 0, background: 'inherit', paddingTop: '8px' }}>
        <motion.button
          type="submit"
          whileHover={ready ? { scale: 1.01 } : {}}
          whileTap={ready ? { scale: 0.99 } : {}}
          disabled={!ready}
          style={{
            width: '100%',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '9px',
            padding: '14px', borderRadius: '12px', border: 'none',
            background: ready
              ? 'linear-gradient(135deg, var(--blue) 0%, #1d4ed8 100%)'
              : 'var(--gray-300)',
            color: 'white', fontWeight: 600, fontSize: '14px', fontFamily: 'inherit',
            cursor: ready ? 'pointer' : 'not-allowed',
            boxShadow: ready ? '0 4px 16px rgba(37,99,235,0.28)' : 'none',
            transition: 'background 0.2s, box-shadow 0.2s',
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
          ) : structureMode ? (
            <>
              <ScanSearch size={16} strokeWidth={2.2} />
              {t('story.btn_structure', 'Analyser la structure')}
            </>
          ) : (
            <>
              <Languages size={16} strokeWidth={2.2} />
              {t('story.btn_translate')}
            </>
          )}
        </motion.button>

        {/* Le bouton désactivé dit POURQUOI il l'est. */}
        {!file && !isTranslating && (
          <span style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px',
            marginTop: '8px', fontSize: '11.5px', color: 'var(--gray-500)',
          }}>
            <Info size={12} strokeWidth={2} />
            {t('story.cta_hint', 'Choisissez un document pour commencer.')}
          </span>
        )}
      </div>

      {/* Action */}
      <div style={{ position: 'sticky', bottom: 0, background: 'inherit', paddingTop: '8px' }}>
        <motion.button
          type="submit"
          whileHover={ready ? { scale: 1.01 } : {}}
          whileTap={ready ? { scale: 0.99 } : {}}
          disabled={!ready}
          style={{
            width: '100%',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '9px',
            padding: '14px', borderRadius: '12px', border: 'none',
            background: ready
              ? 'linear-gradient(135deg, var(--blue) 0%, #1d4ed8 100%)'
              : 'var(--gray-300)',
            color: 'white', fontWeight: 600, fontSize: '14px', fontFamily: 'inherit',
            cursor: ready ? 'pointer' : 'not-allowed',
            boxShadow: ready ? '0 4px 16px rgba(37,99,235,0.28)' : 'none',
            transition: 'background 0.2s, box-shadow 0.2s',
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
          ) : structureMode ? (
            <>
              <ScanSearch size={16} strokeWidth={2.2} />
              {t('story.btn_structure', 'Analyser la structure')}
            </>
          ) : (
            <>
              <Languages size={16} strokeWidth={2.2} />
              {t('story.btn_translate')}
            </>
          )}
        </motion.button>

        {!file && !isTranslating && (
          <span style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px',
            marginTop: '8px', fontSize: '11.5px', color: 'var(--gray-500)',
          }}>
            <Info size={12} strokeWidth={2} />
            {t('story.cta_hint', 'Choisissez un document pour commencer.')}
          </span>
        )}
      </div>
      </>
      ) : null}
    </form>
  );
}
