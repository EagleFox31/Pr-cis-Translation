import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { ChoixPage, PageIllisible, PagesIllisibles, ResultatChoix } from './useDocumentLibrary';

const RELANCE_MS = 3000;
const VIDE: PagesIllisibles = { pages: [], en_cours: [] };

interface Options {
  /** Document dont on suit les pages illisibles (`null` = aucun). */
  docId: string | null;
  load: (id: string) => Promise<PagesIllisibles>;
  choose: (id: string, pages: number[], choix: ChoixPage) => Promise<ResultatChoix>;
  /** Appelé quand le rendu d'une page change : l'aperçu doit être recalculé. */
  onChanged: () => void;
  /** Avancement de la traduction du scan (`null` = pas un scan suivi). L'état
   *  est relu à chaque page terminée et à la fin : les pages illisibles
   *  apparaissent au fil de la lecture, sans relecture périodique. */
  traduction?: { enCours: boolean; pagesFaites: number } | null;
}

/** Vue des pages illisibles d'un scan, passée jusqu'à l'aperçu. */
export interface PagesIllisiblesVue {
  pages: PageIllisible[];
  /** Pages dont la lecture forcée est en cours. */
  enCours: number[];
  /** `true` si le choix a été enregistré (ou la lecture lancée). */
  choisir: (pages: number[], choix: ChoixPage) => Promise<boolean>;
  erreur: string | null;
  occupe: boolean;
  /** Traduction en cours : la décision attend la fin. */
  provisoire: boolean;
  /** Pages blanches du scan (vignette neutre, ni traduite ni à décider). */
  blanches: number[];
}

/** Pages d'un scan que la lecture n'a pas pu traiter : chargement, choix
 *  (original, vide, traduire quand même) et suivi des lectures relancées.
 *  Une page « traduite quand même » réussie quitte la liste. */
export function usePagesIllisibles(
  { docId, load, choose, onChanged, traduction = null }: Options,
): PagesIllisiblesVue {
  const { t } = useTranslation();
  const [etat, setEtat] = useState<PagesIllisibles>(VIDE);
  const [erreur, setErreur] = useState<string | null>(null);
  const [occupe, setOccupe] = useState(false);
  const etatRef = useRef<PagesIllisibles>(VIDE);
  // Incrémenté à chaque choix : une lecture lancée avant, qui revient après,
  // écraserait l'état à jour par un état périmé.
  const version = useRef(0);

  const poser = useCallback((suivant: PagesIllisibles) => {
    etatRef.current = suivant;
    setEtat(suivant);
  }, []);

  // Une lecture relancée qui se termine change le rendu de la page.
  const appliquer = useCallback((suivant: PagesIllisibles) => {
    if (suivant.en_cours.length < etatRef.current.en_cours.length) onChanged();
    poser(suivant);
  }, [onChanged, poser]);

  // Lecture ponctuelle : un échec est rattrapé au tour suivant.
  const relire = useCallback((id: string, vivant: () => boolean) => {
    const v = version.current;
    load(id).then((e) => {
      if (vivant() && v === version.current) appliquer(e);
    }).catch(() => {
      // Traduction terminée en erreur : la liste provisoire n'a plus d'objet.
      if (vivant() && v === version.current && etatRef.current.provisoire) poser(VIDE);
    });
  }, [load, appliquer, poser]);

  useEffect(() => {
    let alive = true;
    version.current += 1;
    poser(VIDE);
    setErreur(null);
    if (docId) relire(docId, () => alive);
    return () => { alive = false; };
  }, [docId, poser, relire]);

  // Une page terminée ou la fin de la traduction : relire l'état (temps réel,
  // piloté par l'avancement déjà reçu, aucune requête entre deux pages).
  const enTraduction = !!traduction?.enCours;
  const signal = traduction ? `${enTraduction}:${traduction.pagesFaites}` : null;
  const dernierSignal = useRef(signal);
  useEffect(() => {
    let alive = true;
    // Passage à `null` compris : fin du suivi d'un document de la bibliothèque.
    if (signal !== dernierSignal.current && docId) relire(docId, () => alive);
    dernierSignal.current = signal;
    return () => { alive = false; };
  }, [signal, docId, relire]);

  // Relecture périodique, seulement là où aucun avancement n'arrive :
  // - une lecture « traduire quand même » relancée après coup ;
  // - une liste encore provisoire alors que la traduction est finie (le
  //   serveur n'a pas encore enregistré le document traduit).
  const suivre = etat.en_cours.length > 0 || (!!etat.provisoire && !enTraduction);
  useEffect(() => {
    if (!suivre || !docId) return;
    let alive = true;
    const id = window.setInterval(() => relire(docId, () => alive), RELANCE_MS);
    return () => { alive = false; window.clearInterval(id); };
  }, [suivre, docId, relire]);

  const choisir = useCallback(async (pages: number[], choix: ChoixPage): Promise<boolean> => {
    if (!docId || pages.length === 0) return false;
    version.current += 1;
    setOccupe(true);
    setErreur(null);
    const res = await choose(docId, pages, choix)
      .catch((): ResultatChoix => ({ ok: false, message: null }));
    const reussi = 'etat' in res;
    if ('etat' in res) {
      if (choix !== 'traduire') onChanged();
      poser(res.etat);
    } else {
      setErreur(res.message ?? t('viewer.scan.error'));
      // L'état a pu changer ailleurs (page déjà lue, autre onglet) : le relire,
      // et recalculer l'aperçu si une page a quitté la liste.
      const avant = etatRef.current.pages.length;
      await load(docId).then((e) => {
        if (e.pages.length < avant) onChanged();
        appliquer(e);
      }).catch(() => {});
    }
    setOccupe(false);
    return reussi;
  }, [docId, choose, load, onChanged, appliquer, poser, t]);

  return { pages: etat.pages, enCours: etat.en_cours, choisir, erreur, occupe,
           provisoire: !!etat.provisoire, blanches: etat.blanches ?? [] };
}
