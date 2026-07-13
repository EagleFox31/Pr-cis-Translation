import { useEffect, useRef, useState } from 'react';
import { motion } from 'motion/react';
import { Loader2, Hourglass, Lock } from 'lucide-react';

interface PdfViewerProps {
  sourceFile?: Blob | null;
  translatedBlob?: Blob | null;
  demoSource?: string;
  demoTarget?: string;
  currentPage: number;
  zoom: number;
  isTrialMode: boolean;
  onPagesLoaded?: (numPages: number) => void;
  className?: string;
  /** La page courante est-elle traduite (streaming) ? Sinon on affiche un
      placeholder à la place du canevas traduit. */
  translatedPageReady?: boolean;
  translatedPageStatus?: string;
  /** Libellés des panneaux (langue source détectée / langue cible). */
  sourceLabel?: string;
  targetLabel?: string;
}

export default function PdfViewer({
  sourceFile,
  translatedBlob,
  demoSource = '/CV_Mbowou_Ibrahim_Pigier.pdf',
  demoTarget = '/CV_Mbowou_Ibrahim_Pigier_TRADUIT.pdf',
  currentPage,
  zoom,
  isTrialMode,
  onPagesLoaded,
  className,
  translatedPageReady = true,
  translatedPageStatus,
  sourceLabel = 'Original',
  targetLabel = 'Traduction',
}: PdfViewerProps) {
  const [cursorPos, setCursorPos] = useState<{ x: number; y: number } | null>(null);
  // True quand le canevas traduit affiche RÉELLEMENT la page courante.
  const [translatedShown, setTranslatedShown] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    const renderTasks: any[] = [];
    const loadingTasks: any[] = [];

    const loadPDFs = async () => {
      const pdfjsLib = (window as any).pdfjsLib;
      if (!pdfjsLib) {
        console.error('PDF.js not loaded');
        return;
      }

      pdfjsLib.GlobalWorkerOptions.workerSrc =
        'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.16.105/pdf.worker.min.js';

      try {
        let pdfSourceOrig: any;
        let pdfSourceTrad: any = null;

        // Le document CHOISI prime toujours. La démo (CV) ne sert que quand
        // aucun document n'est chargé (vitrine). Auparavant, l'absence de
        // traduction — cas normal au DÉMARRAGE du streaming — faisait basculer
        // les DEUX panneaux sur le CV de démo.
        if (sourceFile) {
          // Données passées directement à pdf.js (PAS d'URL blob : l'effet se
          // relance à chaque changement de page/zoom et le cleanup révoquait
          // l'URL pendant que le worker la chargeait encore → blob introuvable).
          const origBuf = await sourceFile.arrayBuffer();
          if (!active) return;
          pdfSourceOrig = pdfjsLib.getDocument({ data: origBuf });
          if (translatedBlob) {
            const tradBuf = await translatedBlob.arrayBuffer();
            if (!active) return;
            pdfSourceTrad = pdfjsLib.getDocument({ data: tradBuf });
          }
        } else if (translatedBlob) {
          // Aperçu depuis la bibliothèque : pas d'original, seulement le traduit.
          const tradBuf = await translatedBlob.arrayBuffer();
          if (!active) return;
          pdfSourceTrad = pdfjsLib.getDocument({ data: tradBuf });
          pdfSourceOrig = pdfjsLib.getDocument(demoSource);
        } else {
          pdfSourceOrig = pdfjsLib.getDocument(demoSource);
          pdfSourceTrad = pdfjsLib.getDocument(demoTarget);
        }
        loadingTasks.push(pdfSourceOrig);
        if (pdfSourceTrad) loadingTasks.push(pdfSourceTrad);

        const pdfOrig = await pdfSourceOrig.promise;
        if (!active) return;
        onPagesLoaded?.(pdfOrig.numPages);

        const pdfTrad = pdfSourceTrad ? await pdfSourceTrad.promise : null;
        if (!active) return;

        const renderPage = async (pdf: any, canvasId: string, pageNum: number) => {
          // Borne la page demandée : un document mono-page recevait encore le
          // numéro de page de l'état précédent → « Invalid page request ».
          const safePage = Math.min(Math.max(1, pageNum), pdf.numPages);
          const page = await pdf.getPage(safePage);
          if (!active) return;
          const canvas = document.getElementById(canvasId) as HTMLCanvasElement;
          if (!canvas) return;

          let containerWidth = 600;
          const scrollEl = document.getElementById('scroll');
          if (scrollEl) {
            containerWidth = (scrollEl.clientWidth - 70) / 2;
          } else {
            containerWidth = canvas.parentElement?.clientWidth || 600;
          }

          const unscaledViewport = page.getViewport({ scale: 1.0 });
          const baseScale = containerWidth / unscaledViewport.width;
          const scale = baseScale * zoom;
          const viewport = page.getViewport({ scale });
          const context = canvas.getContext('2d');
          if (!context) return;

          canvas.height = viewport.height;
          canvas.width = viewport.width;

          const renderContext = { canvasContext: context, viewport };
          const renderTask = page.render(renderContext);
          renderTasks.push(renderTask);
          await renderTask.promise;
        };

        await renderPage(pdfOrig, 'pdf-canvas-original', currentPage);

        // Panneau TRADUIT : n'affiche la page que si le PDF traduit existe, que
        // la page est prête ET présente dedans (sinon le viewer clamperait sur
        // une autre page).
        const tradHasPage = !!pdfTrad && translatedPageReady && currentPage <= pdfTrad.numPages;
        if (tradHasPage) {
          await renderPage(pdfTrad, 'pdf-canvas-translated', currentPage);
          if (isTrialMode) {
            await renderPage(pdfTrad, 'pdf-canvas-translated-clear', currentPage);
          }
          if (active) setTranslatedShown(true);
        } else {
          // Page pas encore traduite : on efface le canevas et on montre le
          // placeholder (dimensionné comme l'original pour un cadre stable).
          if (active) setTranslatedShown(false);
          const canvas = document.getElementById('pdf-canvas-translated') as HTMLCanvasElement;
          const origCanvas = document.getElementById('pdf-canvas-original') as HTMLCanvasElement;
          if (canvas && origCanvas) {
            canvas.width = origCanvas.width;
            canvas.height = origCanvas.height;
            const ctx = canvas.getContext('2d');
            if (ctx) { ctx.fillStyle = '#f8fafc'; ctx.fillRect(0, 0, canvas.width, canvas.height); }
          }
        }
      } catch (error) {
        if (error instanceof Error && error.name === 'RenderingCancelledException') return;
        console.error('Error loading PDF:', error);
      }
    };

    loadPDFs();

    return () => {
      active = false;
      renderTasks.forEach((task) => {
        try {
          task.cancel();
        } catch (e) {
          // ignore
        }
      });
      loadingTasks.forEach((task) => {
        try {
          task.destroy();
        } catch (e) {
          // ignore
        }
      });
    };
  }, [currentPage, zoom, translatedBlob, sourceFile, isTrialMode, demoSource, demoTarget, onPagesLoaded, translatedPageReady]);

  const [isHovering, setIsHovering] = useState(false);

  return (
    <div
      ref={containerRef}
      className={className}
      style={{
        display: 'inline-flex',
        gap: '20px',
        alignItems: 'flex-start',
        minWidth: '100%',
      }}
    >
      {/* Original Panel */}
      <div className="cv-wrap" style={{ flexShrink: 0 }}>
        <span className="cv-lang-badge fr">{sourceLabel}</span>
        <div className="cv" id="cv-fr">
          <canvas
            id="pdf-canvas-original"
            style={{ display: 'block', height: 'auto', margin: '0 auto' }}
          />
        </div>
      </div>

      {/* Separator */}
      <div
        style={{
          width: '1px',
          alignSelf: 'stretch',
          background: 'var(--color-border-tertiary)',
          flexShrink: 0,
        }}
      />

      {/* Translation Panel */}
      <div className="cv-wrap" style={{ flexShrink: 0 }}>
        <span
          className="cv-lang-badge en"
          style={{ background: '#f0fdf4', color: '#15803d' }}
        >
          {targetLabel}
        </span>
        <div
          className="cv trial-viewer"
          id="cv-en"
          style={{
            position: 'relative',
            cursor: isTrialMode ? 'none' : 'auto',
          }}
          onMouseMove={(e) => {
            if (!isTrialMode) return;
            const rect = e.currentTarget.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            setCursorPos({ x, y });
            setIsHovering(true);
          }}
          onMouseEnter={() => setIsHovering(true)}
          onMouseLeave={() => {
            setCursorPos(null);
            setIsHovering(false);
          }}
        >
          {/* Blurred canvas */}
          <canvas
            id="pdf-canvas-translated"
            style={{
              display: 'block',
              height: 'auto',
              margin: '0 auto',
              filter: isTrialMode && translatedShown ? 'brightness(15%) grayscale(100%)' : 'none',
              opacity: isTrialMode && translatedShown ? 0.85 : 1,
            }}
          />

          {/* Placeholder « page en cours / en attente » (streaming) */}
          {!translatedShown && (
            <div
              style={{
                position: 'absolute',
                inset: 0,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '12px',
                background: 'rgba(248,250,252,0.75)',
                backdropFilter: 'blur(1px)',
                color: 'var(--gray-500)',
                textAlign: 'center',
                padding: '20px',
              }}
            >
              {translatedPageStatus && translatedPageStatus !== 'waiting' ? (
                <>
                  <motion.span
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                    style={{ display: 'inline-flex', color: '#2563eb' }}
                  >
                    <Loader2 size={30} strokeWidth={2.2} />
                  </motion.span>
                  <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--gray-700)' }}>
                    {translatedPageStatus === 'extracting' && 'Analyse de la page…'}
                    {translatedPageStatus === 'translating' && 'Traduction en cours…'}
                    {translatedPageStatus === 'rendering' && 'Reconstruction de la mise en page…'}
                  </span>
                </>
              ) : (
                <>
                  <Hourglass size={26} strokeWidth={1.8} style={{ opacity: 0.55 }} />
                  <span style={{ fontSize: '13px' }}>Cette page est en attente de traduction.</span>
                </>
              )}
            </div>
          )}

          {/* Clear canvas (visible under cursor in trial mode) */}
          {isTrialMode && (
            <canvas
              id="pdf-canvas-translated-clear"
              style={{
                display: 'block',
                height: 'auto',
                margin: '0 auto',
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                pointerEvents: 'none',
                opacity: cursorPos ? 1 : 0,
                visibility: cursorPos ? 'visible' : 'hidden',
                WebkitMaskImage: cursorPos ? 'linear-gradient(black, black)' : 'none',
                WebkitMaskSize: cursorPos ? '190px 190px' : '0 0',
                WebkitMaskPosition: cursorPos
                  ? `${cursorPos.x - 95}px ${cursorPos.y - 95}px`
                  : '0 0',
                WebkitMaskRepeat: 'no-repeat',
                maskImage: cursorPos ? 'linear-gradient(black, black)' : 'none',
                maskSize: cursorPos ? '190px 190px' : '0 0',
                maskPosition: cursorPos
                  ? `${cursorPos.x - 95}px ${cursorPos.y - 95}px`
                  : '0 0',
                maskRepeat: 'no-repeat',
              }}
            />
          )}

          {/* Spotlight frame */}
          {isTrialMode && cursorPos && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              style={{
                position: 'absolute',
                width: '190px',
                height: '190px',
                border: '2px solid rgba(37,99,235,0.7)',
                borderRadius: '8px',
                pointerEvents: 'none',
                left: cursorPos.x - 95,
                top: cursorPos.y - 95,
                zIndex: 20,
                boxShadow: '0 0 0 9999px rgba(0,0,0,0.01)',
              }}
            />
          )}

          {/* Trial banner */}
          {isTrialMode && isHovering && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              style={{
                position: 'sticky',
                bottom: '0',
                background: 'rgba(13,27,62,0.92)',
                color: 'white',
                padding: '8px 16px',
                fontSize: '12px',
                textAlign: 'center',
                zIndex: 30,
                backdropFilter: 'blur(4px)',
              }}
            >
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', justifyContent: 'center' }}>
                <Lock size={13} strokeWidth={2.2} />
                Version d'essai — Survolez pour apercevoir ·{' '}
                <a
                  href="#pricing"
                  style={{ color: '#93c5fd', textDecoration: 'underline' }}
                >
                  Acheter pour télécharger
                </a>
              </span>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}
