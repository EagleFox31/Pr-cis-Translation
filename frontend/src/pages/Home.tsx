import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import Navbar from '../components/navbar/Navbar';
import HeroSection from '../components/hero/HeroSection';
import FeaturesGrid from '../components/features/FeaturesGrid';
import ComparisonTable from '../components/comparison/ComparisonTable';
import StorySection from '../components/story/StorySection';
import PricingSection from '../components/pricing/PricingSection';
import AboutSection from '../components/about/AboutSection';
import ToastContainer, { showToast } from '../components/ui/Toast';
import { useTranslation } from '../hooks/useTranslation';
import type { LayoutMode, ShrinkScope } from '../components/preview/LayoutStrategyBar';

/** Construit la spec `layout` envoyée au backend à partir des choix par page. */
function buildLayoutSpec(perPage: Record<number, LayoutMode>, scope: ShrinkScope) {
  const pages: Record<string, LayoutMode> = {};
  for (const [p, m] of Object.entries(perPage)) {
    if (m && m !== 'auto') pages[p] = m;
  }
  return { default: 'auto' as const, pages, shrink_scope: scope };
}

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

  // ---- Per-page layout strategy (chosen after the first conversion) ----
  const { translateFile } = useTranslation();
  const [targetLang, setTargetLang] = useState('en');
  const [sourceLang, setSourceLang] = useState('fr');
  const [perPageMode, setPerPageMode] = useState<Record<number, LayoutMode>>({});
  const [shrinkScope, setShrinkScope] = useState<ShrinkScope>('page');
  const [appliedSig, setAppliedSig] = useState('');
  const [isRegenerating, setIsRegenerating] = useState(false);

  const currentSig = useMemo(
    () => JSON.stringify(buildLayoutSpec(perPageMode, shrinkScope)),
    [perPageMode, shrinkScope]
  );
  const layoutDirty = currentSig !== appliedSig;
  const shrinkUsed = useMemo(
    () => Object.values(perPageMode).some((m) => m === 'shrink'),
    [perPageMode]
  );
  const currentPageMode: LayoutMode = perPageMode[currentPage] || 'auto';

  // ---- Scroll spy ----
  useEffect(() => {
    const sections = document.querySelectorAll('section[id]');
    const observerOptions = { root: null, rootMargin: '-50% 0px', threshold: 0 };

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
    (result: { blob: Blob; filename: string; file: File; targetLang: string; sourceLang: string }) => {
      setTranslatedBlob(result.blob);
      setTranslatedFilename(result.filename);
      setSelectedFile(result.file);
      setTargetLang(result.targetLang);
      setSourceLang(result.sourceLang);
      // First render uses the default "auto" layout everywhere → reset per-page
      // choices and mark the current (empty) layout as the applied one.
      setPerPageMode({});
      setShrinkScope('page');
      setAppliedSig(JSON.stringify(buildLayoutSpec({}, 'page')));
      setShowPreview(true);
    },
    []
  );

  // ---- Apply per-page layout strategy → re-generate (no re-translation) ----
  const handleApplyLayout = useCallback(async () => {
    if (!selectedFile || !layoutDirty || isRegenerating) return;
    setIsRegenerating(true);
    try {
      const res = await translateFile(selectedFile, targetLang, {
        mode: 'preserve' as any,
        fontSizeScale: 1,
        lineHeightScale: 1,
        marginScale: 1,
        layout: buildLayoutSpec(perPageMode, shrinkScope),
      } as any);
      setTranslatedBlob(res.blob);
      setTranslatedFilename(res.filename);
      setAppliedSig(currentSig);
      showToast('success', 'Mise en page appliquée', 'Aperçu mis à jour.');
    } catch (err) {
      showToast('error', 'Échec de la régénération', err instanceof Error ? err.message : 'Erreur inconnue');
    } finally {
      setIsRegenerating(false);
    }
  }, [selectedFile, layoutDirty, isRegenerating, translateFile, targetLang, perPageMode, shrinkScope, currentSig]);

  const handlePageModeChange = useCallback(
    (mode: LayoutMode) => {
      setPerPageMode((prev) => ({ ...prev, [currentPage]: mode }));
    },
    [currentPage]
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

      <Navbar activeSection={activeSection} onNavClick={handleNavClick} />

      <main>
        {/* Ordre SRS RF-1 : le produit (traduction) juste après le hero */}
        <HeroSection />

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
          sourceLang={sourceLang}
          targetLang={targetLang}
          onTranslateComplete={handleTranslateComplete}
          onBack={handleBack}
          onZoomChange={setZoom}
          onPageChange={setCurrentPage}
          onFormattingChange={setFormattingOption}
          onDownload={handleDownload}
          onPagesLoaded={setNumPages}
          pageMode={currentPageMode}
          shrinkScope={shrinkScope}
          shrinkUsed={shrinkUsed}
          layoutDirty={layoutDirty}
          isRegenerating={isRegenerating}
          onPageModeChange={handlePageModeChange}
          onScopeChange={setShrinkScope}
          onApplyLayout={handleApplyLayout}
        />

        <FeaturesGrid />

        <ComparisonTable />

        <PricingSection isAnnual={isAnnual} onAnnualChange={setIsAnnual} />

        <AboutSection />
      </main>
    </div>
  );
}
