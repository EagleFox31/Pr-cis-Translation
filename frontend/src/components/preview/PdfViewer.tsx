import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'motion/react';
import { Loader2, Hourglass, Lock, FileX, ChevronsLeftRight } from 'lucide-react';
import type { PagesIllisiblesVue } from '../../hooks/usePagesIllisibles';
import { chargerPdfjs } from '../../lib/pdfjs';
import ScanPageOverlay from './ScanPageOverlay';
import type { Ajustement } from './ViewerToolbar';

// Largeur du cadre d'aperçu (#scroll) sous laquelle deux volets côte à côte
// tombent sous ~300 px chacun : texte illisible. C'est le CADRE qui compte, pas
// l'écran — une barre latérale peut le rétrécir sur un écran large.
const COMPACT_MAX_PX = 680;
const COMPACT_MARGE_PX = 24;
/** Action secondaire posée sur la page : contour gris neutre, pleine largeur. */
const BOUTON_NEUTRE = {
  width: '100%', padding: '8px 12px', borderRadius: '6px',
  border: '1px solid #94a3b8', background: 'transparent',
  color: 'var(--gray-700)', fontSize: '12.5px', fontWeight: 600,
  fontFamily: 'inherit', cursor: 'pointer',
} as const;

const largeurCadre = () => document.getElementById('scroll')?.clientWidth ?? window.innerWidth;

// Ouvre `blob` dans pdf.js et le garde ouvert tant que le blob ne change pas.
// `garder` : pendant l'ouverture du suivant, continuer d'exposer le précédent
// (aperçu partiel → aperçu partiel suivant, sans passer par le vide).
function usePdfDoc(blob: Blob | null | undefined, garder: boolean) {
  const [doc, setDoc] = useState<any>(null);
  useEffect(() => {
    if (!garder || !blob) setDoc(null);
    if (!blob) return;
    let active = true;
    let livre = false;
    let tache: any = null;
    // Données passées directement à pdf.js (PAS d'URL blob : révoquer l'URL
    // pendant que le worker la lisait encore donnait « blob introuvable »).
    Promise.all([blob.arrayBuffer(), chargerPdfjs()])
      .then(([buf, pdfjsLib]) => {
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
  /** Ajustement actif : la visionneuse calcule alors le zoom et le renvoie par
   *  `onZoomAjuste`. `null` = zoom manuel. */
  ajustement?: Ajustement;
  onZoomAjuste?: (zoom: number) => void;
  /** Rideau de comparaison : UN panneau, la traduction par-dessus l'original. */
  rideau?: boolean;
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
  /** Pages du manque dues aux images demandées. */
  imagesNeeded?: number | null;
  /** Relance du document sans ses images. */
  onTranslateWithoutImages?: () => void;
  /** Essai : quitter l'aperçu pour les tarifs. */
  onUnlock?: () => void;
  /** Fichier disparu du serveur : `translation` = la traduction seule,
   *  `all` = l'original aussi. Remplace le message d'attente. */
  fileMissing?: 'translation' | 'all' | null;
  /** Format attendu de la page tant qu'aucun PDF n'est chargé (cadres vides). */
  formatHint?: 'landscape' | 'portrait';
  /** Pages illisibles du scan : carte de décision sur la page traduite. */
  scanPages?: PagesIllisiblesVue;
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
  ajustement = null,
  onZoomAjuste,
  rideau = false,
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
  imagesNeeded,
  onTranslateWithoutImages,
  onUnlock,
  fileMissing = null,
  formatHint = 'portrait',
  scanPages,
}: PdfViewerProps) {
  const { t } = useTranslation();
  const [cursorPos, setCursorPos] = useState<{ x: number; y: number } | null>(null);
  // True quand le canevas traduit affiche RÉELLEMENT la page courante.
  const [translatedShown, setTranslatedShown] = useState(false);
  // Page réellement dessinée sur le canevas traduit (en retard d'un instant
  // sur `currentPage` lors d'un changement de page).
  const [pagePeinte, setPagePeinte] = useState<number | null>(null);
  // Pages dont le choix vient de changer : le rendu affiché date d'avant, il
  // reste caché jusqu'à l'arrivée du nouveau (`blob` : celui d'avant le choix).
  const [perimees, setPerimees] = useState<{ blob: Blob | null | undefined; pages: number[] } | null>(null);
  const choixVus = useRef<Map<number, string | null> | null>(null);
  const blobCourant = useRef(translatedBlob);
  blobCourant.current = translatedBlob;
  useEffect(() => {
    const maintenant = new Map((scanPages?.pages ?? []).map((p) => [p.page, p.choix] as const));
    const avant = choixVus.current;
    choixVus.current = maintenant;
    if (!avant) return;
    const changees = [...maintenant].filter(([n, c]) => c !== null && avant.has(n) && avant.get(n) !== c)
      .map(([n]) => n);
    if (changees.length === 0) return;
    const blob = blobCourant.current;
    setPerimees((p) => ({ blob, pages: [...(p && p.blob === blob ? p.pages : []), ...changees] }));
  }, [scanPages?.pages]);
  const rendusPerimes = perimees && perimees.blob === translatedBlob ? perimees.pages : [];
  // Orientation de la PAGE COURANTE : paysage → panneaux empilés (vertical),
  // portrait → panneaux côte à côte (horizontal). Détectée par page — un même
  // document peut mêler des pages paysage et portrait, et la disposition suit.
  const [isLandscape, setIsLandscape] = useState(false);
  // Écran ÉTROIT (téléphone) : deux volets côte à côte n'y font que ~150 px
  // chacun, texte illisible. On n'en montre alors qu'UN, en pleine largeur, et
  // une bascule passe de l'un à l'autre — la traduction d'abord.
  const [tailleCadre, setTailleCadre] = useState('');
  const [compact, setCompact] = useState(
    () => typeof window !== 'undefined' && largeurCadre() < COMPACT_MAX_PX,
  );
  const [volet, setVolet] = useState<'source' | 'target'>('target');
  const containerRef = useRef<HTMLDivElement>(null);
  const basculeRef = useRef<HTMLDivElement>(null);
  // Sans original, il n'y a rien à basculer : le volet traduit seul.
  // Rideau : un seul panneau, les deux pages s'y superposent — pas de volet à choisir.
  const voletVu = !compact || rideau ? null : sourceFile ? volet : 'target';
  // Position du rideau (% de la largeur, bord gauche de la traduction), départ à 50 %.
  const [rideauX, setRideauX] = useState(50);
  const sceneRef = useRef<HTMLDivElement>(null);
  useEffect(() => { if (rideau) setRideauX(50); }, [rideau]);
  const deplacerRideau = (clientX: number) => {
    const r = sceneRef.current?.getBoundingClientRect();
    if (!r || r.width <= 0) return;
    setRideauX(Math.round(Math.min(100, Math.max(0, ((clientX - r.left) / r.width) * 100)) * 10) / 10);
  };
  const zoomCourant = useRef(zoom);
  zoomCourant.current = zoom;
  const libelleSource = sourceLabel ?? t('preview.source_label');
  const libelleCible = targetLabel ?? t('preview.target_label');
  // Écran sans survol (tactile) : l'invite d'essai dit « touchez », pas « survolez ».
  const sansSurvol = typeof window !== 'undefined' && !!window.matchMedia?.('(hover: none)').matches;

  useEffect(() => {
    // Hystérésis : la barre de défilement qui apparaît ou disparaît change la
    // largeur de quelques pixels, de quoi faire osciller la bascule (et
    // recharger le PDF à chaque fois) si l'entrée et la sortie coïncidaient.
    const suivre = () => {
      setCompact((c) => {
        const l = largeurCadre();
        return c ? l < COMPACT_MAX_PX + COMPACT_MARGE_PX : l < COMPACT_MAX_PX;
      });
      // Les deux pages sont calées sur la taille du cadre : un bandeau qui
      // apparaît au-dessus (pages scannées, avancement) le réduit. Sans
      // redessin, la page peinte avant garde l'ancienne taille et les deux
      // volets ne correspondent plus.
      const el = document.getElementById('scroll');
      if (el) setTailleCadre(`${el.clientWidth}x${el.clientHeight}`);
    };
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

  // Échelle de base d'un panneau pour une page de `pageW` × `pageH` : celle où
  // elle tient dans le cadre. `zoom` s'y applique ensuite comme multiplicateur.
  const echelleBase = (landscape: boolean, pageW: number, pageH: number, canvas?: HTMLCanvasElement) => {
    let containerWidth = 600;
    let containerHeight = 700;
    const scrollEl = document.getElementById('scroll');
    if (scrollEl) {
      // Écran étroit : le cadre n'a plus de marge (index.css), le volet
      // prend toute la largeur utile — on la lit, on ne la suppose pas.
      const cs = getComputedStyle(scrollEl);
      const padX = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
      // Rideau : UN seul panneau, toute la largeur utile (la bascule a disparu).
      containerWidth = compact || rideau
        ? scrollEl.clientWidth - padX - (rideau ? 2 : 0)
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
      containerHeight = rideau
        ? scrollEl.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom) - 2
        : compact
          ? hDispo - hBascule
          : landscape ? (hDispo - 24) / 2 : hDispo;
    } else {
      containerWidth = canvas?.parentElement?.clientWidth || 600;
    }
    // Caler sur la dimension la PLUS CONTRAIGNANTE : la page tient alors
    // ENTIÈREMENT dans le cadre (largeur ET hauteur). `zoom` agrandit ensuite.
    // Écran étroit : calé sur la LARGEUR, comme une visionneuse — une page
    // entière en hauteur y serait illisible ; on défile verticalement.
    return Math.max(0.05, compact
      ? containerWidth / pageW
      : Math.min(containerWidth / pageW, containerHeight / pageH));
  };

  // Zoom (multiplicateur de `echelleBase`) qui réalise l'ajustement demandé :
  // « page » = les pages visibles tiennent ENTIÈRES dans #scroll (largeur ET
  // hauteur, padding et écarts compris) ; « largeur » = elles en remplissent
  // la largeur. Les cotes sont celles du DOM réel, avec 2 px de marge pour
  // les bordures, de sorte qu'aucune barre de défilement n'apparaisse en « page ».
  const zoomAjuste = (mode: 'page' | 'largeur', pageW: number, pageH: number) => {
    const el = document.getElementById('scroll');
    if (!el) return null;
    const landscape = pageW > pageH;
    const cs = getComputedStyle(el);
    const larg = el.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    const haut = el.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
    let pw: number;
    let ph: number;
    if (rideau) {                 // une seule page
      pw = larg - 2; ph = haut - 2;
    } else if (compact) {         // un volet sous la bascule
      pw = larg - 2;
      ph = haut - 2 - (basculeRef.current ? basculeRef.current.offsetHeight + 12 : 0);
    } else if (landscape) {       // deux pages empilées : 2 écarts de 24 + filet de 1
      pw = larg - 2; ph = (haut - 49 - 4) / 2;
    } else {                      // deux pages côte à côte : 2 écarts de 20 + filet de 1
      pw = (larg - 41 - 4) / 2; ph = haut - 2;
    }
    const cible = mode === 'largeur' ? pw / pageW : Math.min(pw / pageW, ph / pageH);
    const z = cible / echelleBase(landscape, pageW, pageH);
    // Arrondi par défaut : l'arrondi au plus près ferait déborder de quelques pixels.
    return Math.min(4, Math.max(0.25, Math.floor(z * 100) / 100));
  };

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
    const baseScale = echelleBase(landscape, unscaledViewport.width, unscaledViewport.height, canvas);
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
  }, [docOrig, currentPage, zoom, compact, rideau, gabaritVide, tailleCadre]);

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
        .then((ok) => { if (ok && active) { setTranslatedShown(true); setPagePeinte(currentPage); } })
        .catch((e) => signaler(active)(e));
    } else {
      setTranslatedShown(false);
      setPagePeinte(null);
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
  }, [docTrad, docOrig, currentPage, zoom, compact, rideau, translatedPageReady, attendOrig, gabaritVide,
    tailleCadre]);

  // Ajustement actif : le zoom suit la page, le mode de disposition et la
  // taille du cadre. Un écart sous 1 % est ignoré (une barre de défilement qui
  // apparaît change le cadre de quelques pixels : sans seuil, la valeur
  // oscillerait).
  useEffect(() => {
    if (!ajustement || !onZoomAjuste) return;
    let active = true;
    const pdf = docOrig ?? docTrad ?? gabaritVide;
    pdf.getPage(Math.min(Math.max(1, currentPage), pdf.numPages))
      .then((p: any) => {
        if (!active) return;
        const v = p.getViewport({ scale: 1.0 });
        const z = zoomAjuste(ajustement, v.width, v.height);
        if (z !== null && Math.abs(z - zoomCourant.current) >= 0.01) onZoomAjuste(z);
      })
      .catch((e: unknown) => signaler(active)(e));
    return () => { active = false; };
  }, [ajustement, rideau, compact, tailleCadre, currentPage, docOrig, docTrad, gabaritVide, onZoomAjuste]);

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
        // Jamais plus étroit que les deux pages : zoomées, elles débordaient
        // de part et d'autre de cette boîte (centrage), et la partie gauche
        // échappait au défilement horizontal du cadre.
        flexShrink: 0,
      }}
    >
      {compact && sourceFile && !rideau && (
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

      {/* Scène : transparente pour la disposition habituelle (`contents`) ; en
          rideau, c'est la page unique sur laquelle la traduction se superpose. */}
      <div ref={sceneRef} style={rideau ? { position: 'relative', flexShrink: 0 } : { display: 'contents' }}>
      {/* Original Panel */}
      <div
        className="cv-wrap"
        style={{ flexShrink: 0, display: voletVu && voletVu !== 'source' ? 'none' : undefined }}
      >
        {!rideau && <span className="cv-lang-badge fr">{libelleSource}</span>}
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
          display: compact || rideau ? 'none' : undefined,
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
        style={{
          flexShrink: 0,
          display: voletVu && voletVu !== 'target' ? 'none' : undefined,
          // Rideau : calée sur l'original, et découpée depuis la gauche — la
          // traduction n'apparaît qu'à droite de la poignée.
          ...(rideau ? { position: 'absolute', inset: 0, clipPath: `inset(0 0 0 ${rideauX}%)` } : null),
        }}
      >
        {!rideau && (
          <span
            className="cv-lang-badge en"
            style={{ background: '#f0fdf4', color: '#15803d' }}
          >
            {libelleCible}
          </span>
        )}
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
              ...(!translatedShown && ((creditsNeeded && onBuyPages)
                || scanPages?.pages.some((p) => p.page === currentPage))
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
                background: creditsNeeded && onBuyPages ? '#fffefb' : 'rgba(248,250,252,0.75)',
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
                /* Même présentation que la décision « page illisible » : posée
                   sur la page, sans cadre ni ombre, boutons en contour. */
                <div style={{
                  width: '100%', maxWidth: '340px',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px',
                }}>
                  <Lock size={26} strokeWidth={1.8} style={{ color: '#a8a29e' }} aria-hidden />
                  <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--gray-800)',
                                 textWrap: 'balance' }}>
                    {t('preview.credits_insufficient')}
                  </span>
                  {/* Même structure que la carte « page illisible » : le constat,
                      puis ce que chaque bouton ci-dessous permet de faire. */}
                  <span style={{ fontSize: '12.5px', color: 'var(--gray-600)', lineHeight: 1.55,
                                 textAlign: 'justify', textAlignLast: 'center', hyphens: 'auto',
                                 marginTop: '-4px' }}>
                    {creditsReason ?? t('preview.credits_needed', { count: creditsNeeded })}
                    {imagesNeeded ? ` ${t('preview.credits_images', { count: imagesNeeded })}` : ''}
                    {' '}
                    {t(imagesNeeded && onTranslateWithoutImages ? 'preview.credits_hint_images'
                      : pagesCovered && onTranslateCovered ? 'preview.credits_hint_covered'
                      : 'preview.credits_hint_buy')}
                  </span>
                  <button
                    onClick={() => onBuyPages(creditsNeeded)}
                    style={{
                      width: '100%', marginTop: '4px', padding: '9px 14px', borderRadius: '6px',
                      border: '1.5px solid var(--blue)', background: 'transparent',
                      color: 'var(--blue)', fontSize: '13px', fontWeight: 600,
                      fontFamily: 'inherit', cursor: 'pointer',
                    }}
                  >
                    {t('story.buy_pages_cta', { count: creditsNeeded })}
                  </button>
                  {/* Sans les images d'abord : ne garder que les pages couvertes
                      facturerait quand même toutes les images du document. */}
                  {imagesNeeded && onTranslateWithoutImages ? (
                    <button onClick={onTranslateWithoutImages} style={BOUTON_NEUTRE}>
                      {t('preview.translate_without_images')}
                    </button>
                  ) : pagesCovered && onTranslateCovered ? (
                    <button onClick={onTranslateCovered} style={BOUTON_NEUTRE}>
                      {t('preview.translate_covered', { count: pagesCovered })}
                    </button>
                  ) : null}
                </div>
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
                      : translatedPageStatus === 'ocr_attente' ? t('preview.status_ocr_waiting')
                      : translatedPageStatus === 'ocr' ? t('preview.status_ocr')
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

          {/* Page illisible du scan : la décision se prend ici, sur la page. */}
          {scanPages && <ScanPageOverlay page={currentPage} scanPages={scanPages} />}
          {/* Le canevas montre encore une page illisible non décidée (copie de
              l'original) le temps que la suivante soit dessinée : la cacher. */}
          {scanPages && pagePeinte !== null && ((pagePeinte !== currentPage
            && scanPages.pages.some((p) => p.page === pagePeinte
              && (p.choix === null || scanPages.enCours.includes(p.page))))
            || rendusPerimes.includes(pagePeinte)) && (
            <div aria-hidden style={{ position: 'absolute', inset: 0, zIndex: 25, background: '#f8fafc' }} />
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

      {rideau && (
        <>
          <span className="cv-lang-badge fr cv-rideau-etiq">
            {t('viewer.curtain_original', 'Original')}
          </span>
          <span
            className="cv-lang-badge en cv-rideau-etiq droite"
            style={{ background: '#f0fdf4', color: '#15803d' }}
          >
            {t('viewer.curtain_translation', 'Traduction')}
          </span>
          {/* Poignée : souris et tactile (pointer events), flèches du clavier ±5 %.
              Les flèches ne doivent pas changer de page (raccourcis globaux). */}
          <div
            role="slider"
            tabIndex={0}
            className="cv-rideau-poignee"
            style={{ left: `${rideauX}%` }}
            aria-label={t('viewer.curtain_handle', 'Position du rideau de comparaison')}
            aria-orientation="horizontal"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(rideauX)}
            aria-valuetext={`${Math.round(rideauX)} %`}
            onPointerDown={(e) => {
              e.currentTarget.setPointerCapture(e.pointerId);
              deplacerRideau(e.clientX);
            }}
            onPointerMove={(e) => {
              if (e.currentTarget.hasPointerCapture(e.pointerId)) deplacerRideau(e.clientX);
            }}
            onPointerUp={(e) => {
              if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId);
            }}
            onKeyDown={(e) => {
              const pas = e.key === 'ArrowLeft' ? -5 : e.key === 'ArrowRight' ? 5 : 0;
              if (pas === 0) return;
              e.preventDefault();
              e.stopPropagation();
              setRideauX((x) => Math.min(100, Math.max(0, x + pas)));
            }}
          >
            <span aria-hidden><ChevronsLeftRight size={14} strokeWidth={2.4} /></span>
          </div>
        </>
      )}
      </div>
    </div>
  );
}
