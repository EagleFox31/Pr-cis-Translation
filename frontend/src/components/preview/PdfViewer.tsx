import { useEffect, useRef, useState, useCallback } from 'react';
import { motion } from 'motion/react';

interface PdfViewerProps {
  sourceFile?: File | null;
  translatedBlob?: Blob | null;
  demoSource?: string;
  demoTarget?: string;
  currentPage: number;
  zoom: number;
  isTrialMode: boolean;
  onPagesLoaded?: (numPages: number) => void;
  className?: string;
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
}: PdfViewerProps) {
  const [cursorPos, setCursorPos] = useState<{ x: number; y: number } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    let originalUrl: string | null = null;
    let translatedUrl: string | null = null;
    const renderTasks: any[] = [];

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
        let pdfSourceTrad: any;

        if (translatedBlob && sourceFile) {
          translatedUrl = URL.createObjectURL(translatedBlob);
          originalUrl = URL.createObjectURL(sourceFile);
          pdfSourceOrig = pdfjsLib.getDocument(originalUrl);
          pdfSourceTrad = pdfjsLib.getDocument(translatedUrl);
        } else {
          pdfSourceOrig = pdfjsLib.getDocument(demoSource);
          pdfSourceTrad = pdfjsLib.getDocument(demoTarget);
        }

        const pdfOrig = await pdfSourceOrig.promise;
        if (!active) return;
        onPagesLoaded?.(pdfOrig.numPages);

        const pdfTrad = await pdfSourceTrad.promise;
        if (!active) return;

        const renderPage = async (pdf: any, canvasId: string, pageNum: number) => {
          const page = await pdf.getPage(pageNum);
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
        await renderPage(pdfTrad, 'pdf-canvas-translated', currentPage);

        if (isTrialMode) {
          await renderPage(pdfTrad, 'pdf-canvas-translated-clear', currentPage);
        }
      } catch (error) {
        if (error instanceof Error && error.name === 'RenderingCancelledException') return;
        console.error('Error loading PDF:', error);
      }
    };

    loadPDFs();

    return () => {
      active = false;
      if (originalUrl) URL.revokeObjectURL(originalUrl);
      if (translatedUrl) URL.revokeObjectURL(translatedUrl);
      renderTasks.forEach((task) => {
        try {
          task.cancel();
        } catch (e) {
          // ignore
        }
      });
    };
  }, [currentPage, zoom, translatedBlob, sourceFile, isTrialMode, demoSource, demoTarget, onPagesLoaded]);

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
        <span className="cv-lang-badge fr">FR — Original</span>
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
          EN — Traduction
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
              filter: isTrialMode ? 'brightness(15%) grayscale(100%)' : 'none',
              opacity: isTrialMode ? 0.85 : 1,
            }}
          />

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
              🔒 Version d'essai — Survolez pour apercevoir ·{' '}
              <a
                href="#pricing"
                style={{ color: '#93c5fd', textDecoration: 'underline' }}
              >
                Acheter pour télécharger
              </a>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}
