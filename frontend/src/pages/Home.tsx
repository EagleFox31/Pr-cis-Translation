import { useState, useEffect, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import Navbar from '../components/navbar/Navbar';
import HeroSection from '../components/hero/HeroSection';
import FeaturesGrid from '../components/features/FeaturesGrid';
import StorySection from '../components/story/StorySection';
import PricingSection from '../components/pricing/PricingSection';
import AboutSection from '../components/about/AboutSection';
import ToastContainer, { showToast } from '../components/ui/Toast';
import DocumentLibrary from '../components/library/DocumentLibrary';
import { useAuth } from '../contexts/AuthContext';
import { useDocumentLibrary } from '../hooks/useDocumentLibrary';
import { useStreamingTranslation } from '../hooks/useStreamingTranslation';
import { isTrialFor } from '../lib/plans';
import type { TranslateConfig } from '../components/upload/TranslationSection';

export default function Home() {
  const { t } = useTranslation();
  const [isAnnual, setIsAnnual] = useState(true);
  const [activeSection, setActiveSection] = useState('hero');
  const [showPreview, setShowPreview] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [numPages, setNumPages] = useState(1);
  const [zoom, setZoom] = useState(1.0);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [translatedBlob, setTranslatedBlob] = useState<Blob | null>(null);
  const [translatedFilename, setTranslatedFilename] = useState<string>('');
  const [showLibrary, setShowLibrary] = useState(false);
  const [targetLang, setTargetLang] = useState('en');
  // Aperçu ouvert depuis la bibliothèque : le panneau s'affiche tout de suite,
  // ce drapeau dit au viewer de montrer « rendu en cours » au lieu du sablon
  // « page en attente », qui ferait croire à une traduction inachevée.
  const [previewLoading, setPreviewLoading] = useState(false);
  // DEUX compteurs, et non un seul partagé. L'ouverture d'un aperçu et le
  // chargement d'une page sont deux courses distinctes : avec un compteur
  // unique, l'effet de page incrémentait le jeton juste après l'ouverture et
  // périmait le chargement du document SOURCE — le panneau gauche restait vide
  // et la comparaison côte à côte disparaissait.
  const openToken = useRef(0);    // une ouverture d'aperçu
  const pageToken = useRef(0);    // une demande de page
  // Pages déjà reçues (clé `docId:page`) et document dont on possède le rendu
  // COMPLET : c'est ce qui rend la navigation instantanée au retour sur une
  // page, et muette côté réseau quand le serveur a livré tout le document.
  const pageBlobCache = useRef(new Map<string, Blob>());
  const fullDocFor = useRef<string | null>(null);
  // Document de la BIBLIOTHÈQUE en cours d'aperçu (null = traduction en direct,
  // qui reçoit ses pages par le flux et n'a rien à redemander).
  const [libraryDocId, setLibraryDocId] = useState<string | null>(null);

  // ---- Traduction PROGRESSIVE (page par page) ----
  const stream = useStreamingTranslation();
  const { user, refreshUser } = useAuth();

  // Mode ESSAI : DÉRIVÉ du plan, jamais stocké. C'était un `useState(true)`
  // dont le setter n'était appelé nulle part — l'aperçu restait donc assombri
  // et le téléchargement verrouillé pour TOUT LE MONDE, abonnés et admin
  // compris. Un état qui ne change jamais n'est pas un état : c'est un calcul.
  const isTrialMode = isTrialFor(user);

  // ---- Document library ----
  const { documents, refresh, saveDocument, getBlob, getPreviewBlob, getOriginalBlob, deleteDocument, clearAll } = useDocumentLibrary();

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

  // ---- Démarrage de la traduction : l'aperçu s'ouvre IMMÉDIATEMENT, les pages
  //      traduites y apparaissent au fil de l'eau (streaming page par page). ----
  const handleStartTranslate = useCallback(
    (config: TranslateConfig) => {
      // Le catalogue ne propose que des codes de base ('en', 'fr'…) : plus de
      // variante régionale à réduire avant l'envoi.
      const { file, targetLang, pages, debug, precise } = config;
      setSelectedFile(file);
      setTargetLang(targetLang);
      // Une traduction EN DIRECT reçoit ses pages par le flux : elle n'a rien
      // à redemander au serveur. Sans cette remise à zéro, l'effet d'aperçu
      // continuerait de réclamer les pages du document précédent et les
      // poserait par-dessus celles qui arrivent.
      setLibraryDocId(null);
      setPreviewLoading(false);
      setTranslatedBlob(null);
      setTranslatedFilename('');
      setCurrentPage(1);
      setShowPreview(true);

      stream
        .start(file, targetLang, pages, debug, precise)
        .then((result) => {
          setTranslatedBlob(result.blob);
          setTranslatedFilename(result.filename);
          const ext = result.filename.split('.').pop()?.toLowerCase() ?? 'pdf';
          saveDocument(result.blob, result.filename, {
            originalName: file.name,
            targetLang,
            ext,
          });
          // Forfait freemium = 1 page max, on invite à upgrader
          if (user?.plan === 'free') {
            showToast('success', 'Forfait Gratuit — 1 page / mois', 'Passez à Starter pour traduire des documents complets.');
          } else {
            showToast('success', t('story.success_done'), result.filename);
          }
        })
        .catch((err) => {
          const msg = err instanceof Error ? err.message : '';
          showToast('error', t('story.error_default'), msg || undefined);
        });
    },
    [stream, saveDocument, t],
  );

  // ---- Library preview ----
  const handleLibraryPreview = useCallback(
    (req: {
      docId: string;
      filename: string;
      ext: string;
      source: Promise<Blob | undefined>;
    }) => {
      // Chaque ouverture reçoit un jeton. Sans lui, ouvrir A puis B pendant que
      // A charge encore laisse la réponse de A — arrivée en dernier — écraser
      // le document B affiché à l'écran.
      const token = ++openToken.current;
      const fresh = () => openToken.current === token;

      stream.reset();
      setTranslatedBlob(null);
      setSelectedFile(null);
      setTranslatedFilename(req.filename);
      // Caches d'aperçu REMIS À ZÉRO : ils appartiennent à l'ouverture
      // précédente. Les garder servirait les pages d'une traduction
      // potentiellement retraduite depuis.
      pageBlobCache.current.clear();
      fullDocFor.current = null;
      setLibraryDocId(req.docId);
      setCurrentPage(1);
      setPreviewLoading(true);
      setShowLibrary(false);
      setShowPreview(true);   // ← l'aperçu est visible AVANT le premier octet

      // Le fichier source est servi tel quel : il arrive presque tout de suite
      // et remplit le panneau gauche pendant que la traduction se rastérise.
      req.source.then((src) => {
        if (fresh() && src) {
          setSelectedFile(new File([src], req.filename, { type: 'application/pdf' }));
        }
      }).catch(() => { /* panneau gauche vide : le viewer le gère */ });

      // La traduction est chargée par l'effet ci-dessous, page par page.
    },
    [stream],
  );

  // ---- Aperçu bibliothèque : réseau seulement quand on ne SAIT pas ---------
  //
  // Trois niveaux, du plus rapide au plus lent, et on s'arrête au premier :
  //   1. le serveur a déjà envoyé le rendu COMPLET (`X-Render: full`) →
  //      navigation 100 % locale, plus une seule requête ;
  //   2. la page a déjà été visitée → blob repris du cache mémoire, instantané
  //      (revenir sur une page relançait ~10 s de reconstruction serveur) ;
  //   3. sinon seulement, on demande la page au serveur.
  useEffect(() => {
    if (!libraryDocId || !showPreview) return;
    if (fullDocFor.current === libraryDocId) return;          // niveau 1
    const key = `${libraryDocId}:${currentPage}`;
    const hit = pageBlobCache.current.get(key);
    if (hit) { setTranslatedBlob(hit); setPreviewLoading(false); return; }  // niveau 2

    const token = ++pageToken.current;
    setPreviewLoading(true);
    getPreviewBlob(libraryDocId, currentPage)
      .then((res) => {
        // Jeton : tourner vite les pages lance plusieurs requêtes, et rien ne
        // garantit qu'elles reviennent dans l'ordre. Sans lui, une page lente
        // demandée avant écrase la page rapide demandée après.
        if (pageToken.current !== token || !res) return;
        if (res.full) {
          // Tout le document est là : les blobs par page n'ont plus d'objet.
          fullDocFor.current = libraryDocId;
          pageBlobCache.current.clear();
        } else {
          pageBlobCache.current.set(key, res.blob);
          // Borne mémoire : ~3 Mo par blob, on garde les 20 dernières pages
          // visitées (FIFO — Map préserve l'ordre d'insertion).
          while (pageBlobCache.current.size > 20) {
            const oldest = pageBlobCache.current.keys().next().value as string;
            pageBlobCache.current.delete(oldest);
          }
        }
        setTranslatedBlob(res.blob);
      })
      .catch(() => { /* le lecteur garde son écran d'attente */ })
      .finally(() => { if (pageToken.current === token) setPreviewLoading(false); });
  }, [libraryDocId, currentPage, showPreview, getPreviewBlob]);

  // ---- Download (le résultat complet, une fois la traduction terminée) ----
  const handleDownload = useCallback(() => {
    const blob = stream.result?.blob ?? translatedBlob;
    if (blob && translatedFilename) {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = translatedFilename;
      document.body.appendChild(a);
      a.click();
      URL.revokeObjectURL(url);
      document.body.removeChild(a);
    }
  }, [stream.result, translatedBlob, translatedFilename]);

  // ---- Back from preview ----
  const handleBack = useCallback(() => {
    stream.cancel();
    setShowPreview(false);
    setLibraryDocId(null);          // plus d'aperçu ouvert : plus rien à charger
    setPreviewLoading(false);
  }, [stream]);

  // Aperçu du panneau « traduit » : blob final si dispo, sinon PDF partiel
  // (pages déjà prêtes), mis à jour au fil de l'eau pendant le streaming.
  const previewTranslatedBlob = translatedBlob ?? stream.partialBlob;
  const effectiveNumPages = stream.totalPages ?? numPages;

  return (
    <div className="min-h-screen bg-white text-gray-900 font-body">
      <ToastContainer />

      <Navbar
        activeSection={activeSection}
        onNavClick={handleNavClick}
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
        getOriginalBlob={getOriginalBlob}
        onPaid={() => { refresh(); refreshUser(); }}
      />

      <main>
        <HeroSection />

        <FeaturesGrid />

        <StorySection
          showPreview={showPreview}
          translatedBlob={previewTranslatedBlob}
          translatedFilename={translatedFilename}
          selectedFile={selectedFile}
          currentPage={currentPage}
          numPages={effectiveNumPages}
          zoom={zoom}
          isTrialMode={isTrialMode}
          targetLang={targetLang}
          isTranslating={stream.isTranslating}
          pageStatuses={stream.pageStatuses}
          renderedUpTo={stream.renderedUpTo}
          previewRendering={previewLoading}
          onStartTranslate={handleStartTranslate}
          onBack={handleBack}
          onZoomChange={setZoom}
          onPageChange={setCurrentPage}
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
