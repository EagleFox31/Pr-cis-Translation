import { useState, useEffect, useCallback } from 'react';
import Navbar from '../components/navbar/Navbar';
import HeroSection from '../components/hero/HeroSection';
import FeaturesGrid from '../components/features/FeaturesGrid';
import StorySection from '../components/story/StorySection';
import PricingSection from '../components/pricing/PricingSection';
import AboutSection from '../components/about/AboutSection';
import ToastContainer from '../components/ui/Toast';
import DocumentLibrary from '../components/library/DocumentLibrary';
import { useDocumentLibrary } from '../hooks/useDocumentLibrary';

export default function Home() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isAnnual, setIsAnnual] = useState(true);
  const [formattingOption, setFormattingOption] = useState('auto-fit');
  const [activeSection, setActiveSection] = useState('hero');
  const [showPreview, setShowPreview] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [numPages, setNumPages] = useState(1);
  const [zoom, setZoom] = useState(1.0);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [translatedBlob, setTranslatedBlob] = useState<Blob | null>(null);
  const [translatedFilename, setTranslatedFilename] = useState<string>('');
  const [isTrialMode, setIsTrialMode] = useState(true);
  const [showLibrary, setShowLibrary] = useState(false);
  const [targetLang, setTargetLang] = useState('en');

  // ---- Document library ----
  const { documents, saveDocument, getBlob, deleteDocument, clearAll } = useDocumentLibrary();

  // ---- Scroll spy ----
  useEffect(() => {
    const sections = document.querySelectorAll('section[id]');
    const observerOptions = { root: null, rootMargin: '-10% 0px -60% 0px', threshold: 0 };

    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          setActiveSection(entry.target.id);
        }
      });
    }, observerOptions);

    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, []);

  // ---- Preview mode class ----
  useEffect(() => {
    const htmlEl = document.documentElement;
    if (showPreview) {
      htmlEl.classList.add('preview-active');
    } else {
      htmlEl.classList.remove('preview-active');
    }
    return () => htmlEl.classList.remove('preview-active');
  }, [showPreview]);

  // ---- Nav click handler ----
  const handleNavClick = useCallback((sectionId: string) => {
    const el = document.getElementById(sectionId);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  }, []);

  // ---- Translation complete ----
  const handleTranslateComplete = useCallback(
    (result: { blob: Blob; filename: string; file: File; targetLang: string }) => {
      setTranslatedBlob(result.blob);
      setTranslatedFilename(result.filename);
      setSelectedFile(result.file);
      setTargetLang(result.targetLang);
      setShowPreview(true);
      // Sauvegarde automatique dans la bibliothèque
      const ext = result.filename.split('.').pop()?.toLowerCase() ?? 'pdf';
      saveDocument(result.blob, result.filename, {
        originalName: result.file.name,
        targetLang: result.targetLang,
        ext,
      });
    },
    [saveDocument],
  );

  // ---- Library preview ----
  const handleLibraryPreview = useCallback(
    (blob: Blob, filename: string, _ext: string) => {
      setTranslatedBlob(blob);
      setTranslatedFilename(filename);
      setSelectedFile(null);
      setShowLibrary(false);
      setShowPreview(true);
    },
    [],
  );

  // ---- Download ----
  const handleDownload = useCallback(() => {
    if (translatedBlob && translatedFilename) {
      const url = URL.createObjectURL(translatedBlob);
      const a = document.createElement('a');
      a.href = url;
      a.download = translatedFilename;
      document.body.appendChild(a);
      a.click();
      URL.revokeObjectURL(url);
      document.body.removeChild(a);
    }
  }, [translatedBlob, translatedFilename]);

  // ---- Back from preview ----
  const handleBack = useCallback(() => {
    setShowPreview(false);
  }, []);

  return (
    <div className="min-h-screen bg-white text-gray-900 font-body">
      <ToastContainer />

      <Navbar
        activeSection={activeSection}
        onNavClick={handleNavClick}
        docCount={documents.length}
        onLibraryOpen={() => setShowLibrary(true)}
      />

      {/* Fixed lang lines overlay — stays in viewport across all sections */}
      <div className="page-bg-lang-lines">
        <div className="hero-lang-lines">
          <div className="lang-line lang-line-left">
            {[1, 2, 3].map((i) => (
              <span key={i} style={{ display: 'inline-flex', gap: '30px' }}>
                <span>Translation</span><span>•</span>
                <span>Traduction</span><span>•</span>
                <span>Traducción</span><span>•</span>
                <span>Übersetzung</span><span>•</span>
                <span>Traduzione</span><span>•</span>
                <span>Overzetting</span><span>•</span>
                <span>翻訳</span><span>•</span>
                <span>번역</span><span>•</span>
                <span>翻译</span><span>•</span>
                <span>ترجمة</span><span>•</span>
                <span>Перевод</span><span>•</span>
              </span>
            ))}
          </div>
          <div className="lang-line lang-line-right">
            {[1, 2, 3].map((i) => (
              <span key={i} style={{ display: 'inline-flex', gap: '30px' }}>
                <span>Documents</span><span>•</span>
                <span>Actes</span><span>•</span>
                <span>Certificats</span><span>•</span>
                <span>Contrats</span><span>•</span>
                <span>Diplômes</span><span>•</span>
                <span>書類</span><span>•</span>
                <span>문서</span><span>•</span>
                <span>文档</span><span>•</span>
                <span>عقود</span><span>•</span>
                <span>Справки</span><span>•</span>
              </span>
            ))}
          </div>
          <div className="lang-line lang-line-left">
            {[1, 2, 3].map((i) => (
              <span key={i} style={{ display: 'inline-flex', gap: '30px' }}>
                <span>Precision</span><span>•</span>
                <span>Précision</span><span>•</span>
                <span>Precisión</span><span>•</span>
                <span>Präzision</span><span>•</span>
                <span>Precisione</span><span>•</span>
                <span>Precisie</span><span>•</span>
                <span>精度</span><span>•</span>
                <span>정밀도</span><span>•</span>
                <span>精确</span><span>•</span>
                <span>دقة</span><span>•</span>
                <span>Точность</span><span>•</span>
              </span>
            ))}
          </div>
          <div className="lang-line lang-line-right">
            {[1, 2, 3].map((i) => (
              <span key={i} style={{ display: 'inline-flex', gap: '30px' }}>
                <span>AI &amp; Human</span><span>•</span>
                <span>IA &amp; Humain</span><span>•</span>
                <span>IA y Humano</span><span>•</span>
                <span>KI &amp; Mensch</span><span>•</span>
                <span>IA &amp; Umano</span><span>•</span>
                <span>AI &amp; Mens</span><span>•</span>
                <span>AI &amp; 人間</span><span>•</span>
                <span>AI &amp; 인간</span><span>•</span>
                <span>AI &amp; 人类</span><span>•</span>
                <span>ذكاء بشري واصطناعي</span><span>•</span>
              </span>
            ))}
          </div>
        </div>
      </div>

      <DocumentLibrary
        isOpen={showLibrary}
        onClose={() => setShowLibrary(false)}
        documents={documents}
        onPreview={handleLibraryPreview}
        onDelete={deleteDocument}
        onClearAll={clearAll}
        getBlob={getBlob}
      />

      <main>
        <HeroSection />

        <FeaturesGrid />

        <StorySection
          showPreview={showPreview}
          translatedBlob={translatedBlob}
          translatedFilename={translatedFilename}
          selectedFile={selectedFile}
          currentPage={currentPage}
          numPages={numPages}
          zoom={zoom}
          formattingOption={formattingOption}
          isTrialMode={isTrialMode}
          targetLang={targetLang}
          onTranslateComplete={handleTranslateComplete}
          onBack={handleBack}
          onZoomChange={setZoom}
          onPageChange={setCurrentPage}
          onFormattingChange={setFormattingOption}
          onDownload={handleDownload}
          onPagesLoaded={setNumPages}
          onLibraryOpen={() => setShowLibrary(true)}
        />

        <PricingSection isAnnual={isAnnual} onAnnualChange={setIsAnnual} />

        <AboutSection />
      </main>
    </div>
  );
}
