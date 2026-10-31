import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'motion/react';
import { Loader2, Hourglass, Lock, FileX } from 'lucide-react';

// Largeur du cadre d'aperçu (#scroll) sous laquelle deux volets côte à côte
// tombent sous ~300 px chacun : texte illisible. C'est le CADRE qui compte, pas
// l'écran — une barre latérale peut le rétrécir sur un écran large.
const COMPACT_MAX_PX = 680;
const COMPACT_MARGE_PX = 24;

const largeurCadre = () => document.getElementById('scroll')?.clientWidth ?? window.innerWidth;

// Ouvre `blob` dans pdf.js et le garde ouvert tant que le blob ne change pas.
// `garder` : pendant l'ouverture du suivant, continuer d'exposer le précédent
// (aperçu partiel → aperçu partiel suivant, sans passer par le vide).
function usePdfDoc(blob: Blob | null | undefined, garder: boolean) {
  const [doc, setDoc] = useState<any>(null);
  useEffect(() => {
    if (!garder || !blob) setDoc(null);
    if (!blob) return;
    const pdfjsLib = (window as any).pdfjsLib;
    if (!pdfjsLib) {
      console.error('PDF.js not loaded');
      return;
    }
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.16.105/pdf.worker.min.js';
    let active = true;
    let livre = false;
    let tache: any = null;
    // Données passées directement à pdf.js (PAS d'URL blob : révoquer l'URL
    // pendant que le worker la lisait encore donnait « blob introuvable »).
    blob.arrayBuffer()
      .then((buf) => {
        if (!active) return null;
        tache = pdfjsLib.getDocument({ data: buf });
        return tache.promise;
      })
      .then((pdf) => {
        if (!active || !pdf) return;
        livre = true;
        setDoc(pdf);
      })
      .catch((error) => {
        // Inactif : c'est notre propre `destroy()` qui fait rejeter.
        if (active) console.error('Error loading PDF:', error);
      });
    return () => {
      active = false;
      // Pas encore livré : personne d'autre ne le fermera. Livré : il sera
      // fermé quand son successeur l'aura remplacé (effet ci-dessous).
      if (!livre && tache) { try { tache.destroy(); } catch { /* déjà fermé */ } }
    };
  }, [blob, garder]);
  // Ferme chaque document quand un autre le remplace, ou au démontage.
  useEffect(() => () => { try { doc?.destroy(); } catch { /* déjà fermé */ } }, [doc]);
  return doc;
}

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
  /** true = chargement en cours (ne PAS afficher la démo). */
  previewLoading?: boolean;
  /** Manque de crédits (402) : pages à régler. Le panneau traduit affiche
   *  l'invitation à payer, avec le bouton dessous, au lieu du message d'attente. */
  creditsNeeded?: number | null;
  onBuyPages?: (pages: number) => void;
  /** Pages déjà couvertes par le solde, si on peut ne traduire qu'elles. */
  pagesCovered?: number | null;
  /** Motif du refus à afficher au-dessus de l'achat (pages offertes refusées
   *  par l'anti-abus). `null` = manque de crédits ordinaire. */
  creditsReason?: string | null;
  /** Relance en ne traduisant que les pages couvertes. */
  onTranslateCovered?: () => void;
  /** Essai : quitter l'aperçu pour les tarifs. */
  onUnlock?: () => void;
  /** Fichier disparu du serveur : `translation` = la traduction seule,
   *  `all` = l'original aussi. Remplace le message d'attente. */
  fileMissing?: 'translation' | 'all' | null;
  /** Format attendu de la page tant qu'aucun PDF n'est chargé (cadres vides). */
  formatHint?: 'landscape' | 'portrait';
}

export default function PdfViewer({
  sourceFile,
  translatedBlob,
  // Vitrine : la page de journal montre les cas qui comptent (colonnes,
  // manchette, encadrés, filets) là où un CV n'en montrait aucun.
  demoSource = '/demo_journal_avant.pdf',
  demoTarget = '/demo_journal_apres.pdf',
  currentPage,
  zoom,
  isTrialMode,
  onPagesLoaded,
  className,
  translatedPageReady = true,
  translatedPageStatus,
  sourceLabel,
  targetLabel,
  previewLoading = false,
  creditsNeeded,
  onBuyPages,
  pagesCovered,
  creditsReason,
  onTranslateCovered,
  onUnlock,
  fileMissing = null,
  formatHint = 'portrait',
}: PdfViewerProps) {
  const { t } = useTranslation();
  const [cursorPos, setCursorPos] = useState<{ x: number; y: number } | null>(null);
  // True quand le canevas traduit affiche RÉELLEMENT la page courante.
  const [translatedShown, setTranslatedShown] = useState(false);
  // Orientation de la PAGE COURANTE : paysage → panneaux empilés (vertical),
  // portrait → panneaux côte à côte (horizontal). Détectée par page — un même
  // document peut mêler des pages paysage et portrait, et la disposition suit.
  const [isLandscape, setIsLandscape] = useState(false);
  // Écran ÉTROIT (téléphone) : deux volets côte à côte n'y font que ~150 px
  // chacun, texte illisible. On n'en montre alors qu'UN, en pleine largeur, et
  // une bascule passe de l'un à l'autre — la traduction d'abord.
  const [compact, setCompact] = useState(
    () => typeof window !== 'undefined' && largeurCadre() < COMPACT_MAX_PX,
  );
  const [volet, setVolet] = useState<'source' | 'target'>('target');
  const containerRef = useRef<HTMLDivElement>(null);
  const basculeRef = useRef<HTMLDivElement>(null);
  // Sans original, il n'y a rien à basculer : le volet traduit seul.
  const voletVu = !compact ? null : sourceFile ? volet : 'target';
  const libelleSource = sourceLabel ?? t('preview.source_label');
  const libelleCible = targetLabel ?? t('preview.target_label');
  // Écran sans survol (tactile) : l'invite d'essai dit « touchez », pas « survolez ».
  const sansSurvol = typeof window !== 'undefined' && !!window.matchMedia?.('(hover: none)').matches;

  useEffect(() => {
    // Hystérésis : la barre de défilement qui apparaît ou disparaît change la
    // largeur de quelques pixels, de quoi faire osciller la bascule (et
    // recharger le PDF à chaque fois) si l'entrée et la sortie coïncidaient.
    const suivre = () => setCompact((c) => {
      const l = largeurCadre();
      return c ? l < COMPACT_MAX_PX + COMPACT_MARGE_PX : l < COMPACT_MAX_PX;
    });
    suivre();   // le cadre a pu changer entre le premier rendu et cet effet
    const cadre = document.getElementById('scroll');
    if (cadre && typeof ResizeObserver !== 'undefined') {
      const ro = new ResizeObserver(suivre);
      ro.observe(cadre);
      return () => ro.disconnect();
    }
    window.addEventListener('resize', suivre);
    return () => window.removeEventListener('resize', suivre);
  }, []);

  // Documents OUVERTS une fois par blob. L'ancien effet rouvrait les DEUX
  // documents et redessinait les DEUX panneaux à chaque aperçu partiel reçu :
  // chaque nouvelle page traduite faisait clignoter toutes les autres.
  // Le traduit garde l'ancien document affiché pendant que le suivant s'ouvre ;
  // l'original, lui, change de document — on ne montre pas le précédent.
  const docOrig = usePdfDoc(sourceFile, false);
  const docTrad = usePdfDoc(translatedBlob, true);
  // Gabarit sans contenu : donne aux cadres le format du document (16:9 pour
  // une présentation, A4 sinon) avant l'arrivée du PDF — ou s'il n'arrive pas.
  const gabaritVide = useMemo(() => {
    const [w, h] = formatHint === 'landscape' ? [960, 540] : [595, 842];
    const page = { getViewport: ({ scale }: { scale: number }) => ({ width: w * scale, height: h * scale }) };
    return { numPages: 1, getPage: async () => page };
  }, [formatHint]);

  // L'original se peint AVANT la traduction : un document rouvert a souvent sa
  // traduction prête avant sa source, et la droite s'affichait seule. Le
  // traduit attend que l'original attendu soit peint — 4 s au plus, pour
  // qu'une source en échec ne bloque jamais la traduction.
  const [origPeint, setOrigPeint] = useState<any>(null);
  const [delaiOrig, setDelaiOrig] = useState(false);
  useEffect(() => {
    setDelaiOrig(false);
    if (!sourceFile) return;
    const t = setTimeout(() => setDelaiOrig(true), 4000);
    return () => clearTimeout(t);
  }, [sourceFile]);
  const attendOrig = !!sourceFile && !delaiOrig && (!docOrig || origPeint !== docOrig);

  // Mesure la page `pageNum` de `pdf` pour le cadre courant.
  const mesurer = async (pdf: any, pageNum: number, canvas: HTMLCanvasElement) => {
    // Borne la page demandée : un document mono-page recevait encore le
    // numéro de page de l'état précédent → « Invalid page request ».
    const page = await pdf.getPage(Math.min(Math.max(1, pageNum), pdf.numPages));
    const unscaledViewport = page.getViewport({ scale: 1.0 });
    // Paysage : chaque panneau prend toute la largeur (empilés verticalement,
    // donc lisibles). Portrait : chaque panneau prend la moitié (côte à côte).
    // La valeur est LOCALE, jamais l'état : un `setIsLandscape` ne prend effet
    // qu'au rendu suivant, et cadrait mal la première frame.
    const landscape = unscaledViewport.width > unscaledViewport.height;
    let containerWidth = 600;
    let containerHeight = 700;
    const scrollEl = document.getElementById('scroll');
    if (scrollEl) {
      // Écran étroit : le cadre n'a plus de marge (index.css), le volet
      // prend toute la largeur utile — on la lit, on ne la suppose pas.
      const cs = getComputedStyle(scrollEl);
      const padX = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
      containerWidth = compact
        ? scrollEl.clientWidth - padX
        : landscape
          ? scrollEl.clientWidth - 24
          : (scrollEl.clientWidth - 70) / 2;
      // Hauteur disponible : le conteneur moins son padding (24px × 2) et
      // la hauteur du badge de langue au-dessus de chaque panneau (~34px).
      // Paysage : deux panneaux EMPILÉS → chacun a la MOITIÉ de la hauteur.
      // Écran étroit : un seul volet visible, sous la bascule (sa hauteur
      // mesurée + l'écart de 12px qui la sépare du volet).
      const hDispo = scrollEl.clientHeight - 48 - 34;
      const hBascule = basculeRef.current ? basculeRef.current.offsetHeight + 12 : 0;
      containerHeight = compact
        ? hDispo - hBascule
        : landscape ? (hDispo - 24) / 2 : hDispo;
    } else {
      containerWidth = canvas.parentElement?.clientWidth || 600;
    }
    // Caler sur la dimension la PLUS CONTRAIGNANTE : la page tient alors
    // ENTIÈREMENT dans le cadre (largeur ET hauteur). `zoom` agrandit ensuite.
    // Écran étroit : calé sur la LARGEUR, comme une visionneuse — une page
    // entière en hauteur y serait illisible ; on défile verticalement.
    const baseScale = Math.max(0.05, compact
      ? containerWidth / unscaledViewport.width
      : Math.min(
        containerWidth / unscaledViewport.width,
        containerHeight / unscaledViewport.height,
      ));
    const viewport = page.getViewport({ scale: baseScale * zoom });
    // Rendu à la densité de l'écran (×2, ×3 sur téléphone), affiché à la
    // taille CSS du viewport : sans cela le texte est flou.
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    return {
      page, viewport, dpr,
      w: Math.floor(viewport.width * dpr), h: Math.floor(viewport.height * dpr),
      cssW: `${Math.floor(viewport.width)}px`, cssH: `${Math.floor(viewport.height)}px`,
    };
  };

  // Donne au canevas visible sa taille, SANS l'effacer si elle n'a pas changé
  // (affecter `width` vide le canevas, même à valeur égale).
  const dimensionner = (canvas: HTMLCanvasElement, m: { w: number; h: number; cssW: string; cssH: string }) => {
    if (canvas.width !== m.w) canvas.width = m.w;
    if (canvas.height !== m.h) canvas.height = m.h;
    if (canvas.style.width !== m.cssW) canvas.style.width = m.cssW;
    if (canvas.style.height !== m.cssH) canvas.style.height = m.cssH;
  };

  // Dessine HORS ÉCRAN, puis copie d'un coup sur le canevas visible. Dessiner
  // directement dessus le vidait d'abord, puis le laissait blanc le temps du
  // rendu : c'était le clignotement. Ici l'image précédente reste en place
  // jusqu'à ce que la suivante soit entière.
  const peindre = async (pdf: any, canvasId: string, estActif: () => boolean, taches: any[]) => {
    const canvas = document.getElementById(canvasId) as HTMLCanvasElement | null;
    if (!canvas) return false;
    const m = await mesurer(pdf, currentPage, canvas);
    if (!estActif()) return false;
    const horsEcran = document.createElement('canvas');
    horsEcran.width = m.w;
    horsEcran.height = m.h;
    const ctx = horsEcran.getContext('2d');
    if (!ctx) return false;
    const tache = m.page.render({
      canvasContext: ctx, viewport: m.viewport,
      transform: m.dpr !== 1 ? [m.dpr, 0, 0, m.dpr, 0, 0] : undefined,
    });
    taches.push(tache);
    await tache.promise;
    if (!estActif()) return false;
    dimensionner(canvas, m);
    canvas.getContext('2d')?.drawImage(horsEcran, 0, 0);
    return true;
  };

  // Un effet démonté a DÉJÀ annulé ses rendus : le rejet qui arrive est celui
  // qu'on a demandé. On ne signale que ce qui casse un rendu ENCORE attendu.
  const signaler = (actif: boolean) => (error: unknown) => {
    if (!actif) return;
    if (error instanceof Error && error.name === 'RenderingCancelledException') return;
    console.error('Error rendering PDF:', error);
  };

  // Pagination et orientation : suivent l'original quand il existe, le
  // traduit sinon (un aperçu sans source resterait bloqué sur une page).
  useEffect(() => {
    const pdf = docOrig ?? docTrad;
    if (!pdf) { setIsLandscape(formatHint === 'landscape'); return; }
    let active = true;
    onPagesLoaded?.(pdf.numPages);
    pdf.getPage(Math.min(Math.max(1, currentPage), pdf.numPages))
      .then((p: any) => {
        if (!active) return;
        const v = p.getViewport({ scale: 1.0 });
        setIsLandscape(v.width > v.height);
      })
      .catch((e) => signaler(active)(e));
    return () => { active = false; };
  }, [docOrig, docTrad, currentPage, onPagesLoaded, formatHint]);

  // Panneau ORIGINAL : ne dépend que de son document, jamais du traduit.
  useEffect(() => {
    let active = true;
    const taches: any[] = [];
    if (docOrig) {
      peindre(docOrig, 'pdf-canvas-original', () => active, taches)
        .then((ok) => { if (ok && active) setOrigPeint(docOrig); })
        .catch((e) => signaler(active)(e));
    } else {
      // Pas de source : panneau VIDE plutôt qu'un document étranger, mais au
      // format du document.
      const canvas = document.getElementById('pdf-canvas-original') as HTMLCanvasElement | null;
      if (canvas) {
        mesurer(gabaritVide, currentPage, canvas).then((m) => {
          if (!active) return;
          dimensionner(canvas, m);
          const ctx = canvas.getContext('2d');
          if (ctx) { ctx.fillStyle = '#f8fafc'; ctx.fillRect(0, 0, canvas.width, canvas.height); }
        }).catch((e) => signaler(active)(e));
      }
    }
    return () => {
      active = false;
      taches.forEach((t) => { try { t.cancel(); } catch { /* déjà fini */ } });
    };
  }, [docOrig, currentPage, zoom, compact, gabaritVide]);

  // Panneau TRADUIT : la page n'y est dessinée que si le serveur l'a déclarée
  // traduite ET qu'elle existe dans le document. Sinon : un fond neutre à la
  // taille de la page, sous le message d'attente — JAMAIS l'original en repli.
  useEffect(() => {
    let active = true;
    const taches: any[] = [];
    if (attendOrig) return;
    const pret = !!docTrad && translatedPageReady && currentPage <= docTrad.numPages;
    if (pret) {
      peindre(docTrad, 'pdf-canvas-translated', () => active, taches)
        .then((ok) => { if (ok && active) setTranslatedShown(true); })
        .catch((e) => signaler(active)(e));
    } else {
      setTranslatedShown(false);
      const canvas = document.getElementById('pdf-canvas-translated') as HTMLCanvasElement | null;
      const gabarit = docOrig ?? docTrad ?? gabaritVide;
      if (canvas) {
        mesurer(gabarit, currentPage, canvas).then((m) => {
          if (!active) return;
          dimensionner(canvas, m);
          const ctx = canvas.getContext('2d');
          if (ctx) { ctx.fillStyle = '#f8fafc'; ctx.fillRect(0, 0, canvas.width, canvas.height); }
        }).catch((e) => signaler(active)(e));
      }
    }
    return () => {
      active = false;
      taches.forEach((t) => { try { t.cancel(); } catch { /* déjà fini */ } });
    };
  }, [docTrad, docOrig, currentPage, zoom, compact, translatedPageReady, attendOrig, gabaritVide]);

  const [isHovering, setIsHovering] = useState(false);

  return (
    <div
      ref={containerRef}
      className={className}
      style={{
        display: 'inline-flex',
        flexDirection: isLandscape || compact ? 'column' : 'row',
        gap: compact ? '12px' : isLandscape ? '24px' : '20px',
        alignItems: 'center',
        justifyContent: 'center',   // panneaux avant/après centrés dans le cadre
        minWidth: '100%',
      }}
    >
      {compact && sourceFile && (
        <div ref={basculeRef} className="cv-bascule" role="group" aria-label={t('preview.toggle_label')}>
          {(['source', 'target'] as const).map((v) => (
            <button
              key={v}
              type="button"
              aria-pressed={volet === v}
              onClick={() => setVolet(v)}
            >
              {v === 'source' ? libelleSource : libelleCible}
            </button>
          ))}
        </div>
      )}

      {/* Original Panel */}
      <div
        className="cv-wrap"
        style={{ flexShrink: 0, display: voletVu && voletVu !== 'source' ? 'none' : undefined }}
      >
        <span className="cv-lang-badge fr">{libelleSource}</span>
        <div className="cv" id="cv-fr">
          <canvas
            id="pdf-canvas-original"
            style={{ display: 'block', height: 'auto', margin: '0 auto' }}
          />
        </div>
      </div>

      {/* Séparateur : horizontal quand les panneaux sont empilés (paysage),
          vertical quand ils sont côte à côte (portrait) */}
      <div
        style={{
          display: compact ? 'none' : undefined,
          width: isLandscape ? '100%' : '1px',
          height: isLandscape ? '1px' : undefined,
          alignSelf: 'stretch',
          background: 'var(--color-border-tertiary)',
          flexShrink: 0,
        }}
      />

      {/* Translation Panel */}
      <div
        className="cv-wrap"
        style={{ flexShrink: 0, display: voletVu && voletVu !== 'target' ? 'none' : undefined }}
      >
        <span
          className="cv-lang-badge en"
          style={{ background: '#f0fdf4', color: '#15803d' }}
        >
          {libelleCible}
        </span>
        <div
          className="cv trial-viewer"
          id="cv-en"
          style={{ position: 'relative' }}
        >
          {/* Pile canevas + surcouches, calée EXACTEMENT sur la taille du canevas
              (donc à la même échelle que le zoom). On mesure le curseur ICI, pas
              sur `cv-en` : le canevas est centré (`margin:auto`), et sa marge de
              centrage change avec le zoom. Repérer le masque et le cadre dans le
              référentiel de `cv-en` les décalait d'autant — d'où le décalage au
              zoom. Dans cette pile, tout partage le repère du canevas. */}
          <div
            style={{
              position: 'relative',
              width: 'fit-content',
              margin: '0 auto',
              // Contient l'ombre portée géante du voile d'essai : elle ne doit
              // assombrir QUE le document, pas déborder autour.
              overflow: 'hidden',
              // Refus pour crédits : rien n'a été dessiné, le canevas garde sa
              // taille par défaut (300×150) et rognait les deux boutons.
              ...(!translatedShown && creditsNeeded && onBuyPages
                ? { minWidth: '320px', minHeight: '300px' } : null),
              // Curseur masqué seulement là où le voile le remplace : sur l'écran
              // « pages à régler » ou d'attente, l'utilisateur doit le voir.
              cursor: isTrialMode && translatedShown ? 'none' : 'auto',
            }}
            onMouseMove={(e) => {
              if (!isTrialMode) return;
              const rect = e.currentTarget.getBoundingClientRect();
              setCursorPos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
              setIsHovering(true);
            }}
            onMouseEnter={() => setIsHovering(true)}
            onMouseLeave={() => { setCursorPos(null); setIsHovering(false); }}
            // Écran tactile : pas de survol. Toucher (ou glisser) place le trou,
            // qui reste là au lâcher — sinon la traduction resterait toute voilée.
            onTouchStart={(e) => {
              if (!isTrialMode) return;
              const rect = e.currentTarget.getBoundingClientRect();
              const tp = e.touches[0];
              setCursorPos({ x: tp.clientX - rect.left, y: tp.clientY - rect.top });
              setIsHovering(true);
            }}
            onTouchMove={(e) => {
              if (!isTrialMode) return;
              const rect = e.currentTarget.getBoundingClientRect();
              const tp = e.touches[0];
              setCursorPos({ x: tp.clientX - rect.left, y: tp.clientY - rect.top });
            }}
          >
          {/* Canevas traduit — UNIQUE. En essai il n'est pas filtré : c'est le
              voile au-dessus qui l'assombrit, en laissant un trou sous le curseur. */}
          <canvas
            id="pdf-canvas-translated"
            style={{ display: 'block', height: 'auto' }}
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
              {creditsNeeded && onBuyPages ? (
                /* Manque de crédits : ici, dans le panneau traduit, on dit
                   simplement qu'il faut régler les pages — et le bouton juste
                   dessous lance le paiement. Pas de bannière ailleurs. */
                <>
                  <Lock size={26} strokeWidth={1.8} style={{ color: 'var(--blue)' }} />
                  <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--gray-900)', maxWidth: '280px' }}>
                    {t('preview.credits_insufficient')}
                  </span>
                  <span style={{ fontSize: '12.5px', color: 'var(--gray-600)', maxWidth: '280px', marginTop: '-6px' }}>
                    {creditsReason ?? t('preview.credits_needed', { count: creditsNeeded })}
                  </span>
                  <button
                    onClick={() => onBuyPages(creditsNeeded)}
                    style={{
                      marginTop: '4px', padding: '10px 20px', borderRadius: '10px', border: 'none',
                      background: 'linear-gradient(135deg, var(--blue) 0%, #1d4ed8 100%)',
                      color: 'white', fontSize: '13px', fontWeight: 600,
                      fontFamily: 'inherit', cursor: 'pointer',
                      boxShadow: '0 4px 14px rgba(37,99,235,0.28)',
                    }}
                  >
                    {t('story.buy_pages_cta', { count: creditsNeeded })}
                  </button>
                  {pagesCovered && onTranslateCovered ? (
                    <button
                      onClick={onTranslateCovered}
                      style={{
                        padding: '8px 16px', borderRadius: '10px',
                        border: '1px solid var(--gray-300)', background: 'white',
                        color: 'var(--gray-700)', fontSize: '12.5px', fontWeight: 600,
                        fontFamily: 'inherit', cursor: 'pointer',
                      }}
                    >
                      {t('preview.translate_covered', { count: pagesCovered })}
                    </button>
                  ) : null}
                </>
              ) : fileMissing ? (
                /* Fichier disparu du serveur : rien à attendre, on dit quoi faire. */
                <>
                  <FileX size={26} strokeWidth={1.8} style={{ opacity: 0.6 }} />
                  <span style={{ fontSize: '13px', maxWidth: '280px' }}>
                    {t(fileMissing === 'all' ? 'preview.file_missing' : 'preview.translation_missing')}
                  </span>
                </>
              ) : translatedPageStatus || previewLoading ? (
                /* Traduction en marche : un chargement et l'ÉTAPE, rien d'autre.
                   Tant qu'aucun aperçu traduit n'existe, l'étape est la
                   préparation ; ensuite, celle de la page (en attente comprise :
                   pour l'utilisateur, elle est « en cours de traduction »). */
                <>
                  <motion.span
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                    style={{ display: 'inline-flex', color: '#2563eb' }}
                  >
                    <Loader2 size={30} strokeWidth={2.2} />
                  </motion.span>
                  <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--gray-700)' }}>
                    {!docTrad || previewLoading ? t('preview.loading')
                      : translatedPageStatus === 'extracting' ? t('preview.status_extracting')
                      : translatedPageStatus === 'rendering' ? t('preview.status_rendering')
                      : t('preview.status_translating')}
                  </span>
                </>
              ) : (
                <>
                  <Hourglass size={26} strokeWidth={1.8} style={{ opacity: 0.55 }} />
                  <span style={{ fontSize: '13px' }}>{t('preview.page_pending')}</span>
                </>
              )}
            </div>
          )}

          {/* Voile d'essai : tout est assombri SAUF une fenêtre sous le curseur.
              Réalisé par l'ombre portée géante d'un petit cadre — donc un SEUL
              canevas, aucune couche « nette » à aligner (c'était la source du
              décalage). Sans curseur : voile plein, rien n'est lisible. */}
          {isTrialMode && translatedShown && (
            cursorPos ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                style={{
                  position: 'absolute',
                  width: '190px',
                  height: '190px',
                  left: cursorPos.x - 95,
                  top: cursorPos.y - 95,
                  border: '2px solid rgba(37,99,235,0.7)',
                  borderRadius: '8px',
                  pointerEvents: 'none',
                  zIndex: 20,
                  boxShadow: '0 0 0 9999px rgba(13,27,62,0.86)',
                }}
              />
            ) : (
              <div style={{
                position: 'absolute', inset: 0,
                background: 'rgba(13,27,62,0.86)', pointerEvents: 'none',
              }} />
            )
          )}

          </div>

          {/* Bandeau d'essai — hors de la pile, collant en bas de cv-en. Affiché
              dès que la page traduite l'est (pas seulement au survol : c'est lui
              qui dit QU'il faut survoler). Une seule ligne, jamais plus large
              que la page : la consigne se tronque, le lien reste entier. */}
          {isTrialMode && translatedShown && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              style={{
                position: 'sticky',
                bottom: '0',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
                width: '100%', boxSizing: 'border-box', minWidth: 0,
                background: 'rgba(13,27,62,0.92)',
                color: 'white',
                padding: '7px 10px',
                fontSize: '12px',
                whiteSpace: 'nowrap',
                zIndex: 30,
                backdropFilter: 'blur(4px)',
              }}
            >
              <Lock size={12} strokeWidth={2.2} style={{ flexShrink: 0 }} />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', minWidth: 0 }}>
                {t(sansSurvol ? 'preview.trial_touch' : 'preview.trial_hover')}
              </span>
              <a
                href="#pricing"
                onClick={(e) => { if (onUnlock) { e.preventDefault(); onUnlock(); } }}
                style={{ color: '#93c5fd', textDecoration: 'underline', flexShrink: 0 }}
              >
                {t('preview.trial_buy')}
              </a>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}
