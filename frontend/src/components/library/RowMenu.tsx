/**
 * Menu « … » d'une ligne de liste (document) ou de la liste elle-même.
 *
 * Contrat clavier et lecteur d'écran (fiche d'intégration, §5) :
 *   • le bouton porte `aria-haspopup="menu"` et `aria-expanded` ;
 *   • à l'ouverture, le focus va sur la première entrée ; flèches haut/bas,
 *     Début/Fin se déplacent ; Échap ferme ET rend le focus au bouton ; Tab
 *     referme et laisse le focus suivre son cours ;
 *   • un seul menu est ouvert à la fois : l'ouverture de l'un ferme les autres,
 *     comme un clic à l'extérieur ;
 *   • si le menu déborde sous le bas de la liste, il s'ouvre vers le haut.
 *
 *   • une entrée peut demander une confirmation : le menu passe alors à un 2e
 *     état (« Confirmer… » en danger, « Annuler »), le focus sur la première ;
 *     Annuler revient au 1er état et rend le focus à l'entrée d'origine ;
 *   • après une entrée, le focus revient au bouton du menu — sauf si l'action
 *     ouvre une fenêtre (elle gère le focus) ou supprime la ligne (le focus va
 *     à la ligne voisine, sinon au titre de la section).
 *
 * Échap est capté avant le tiroir : refermer un menu ne doit pas fermer tout
 * le panneau.
 */
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import type { KeyboardEvent, ReactNode } from 'react';
import { MoreHorizontal } from 'lucide-react';

/** Où va le focus quand l'entrée a été choisie. */
export type RowMenuApres = 'bouton' | 'fenetre' | 'ligne';

export interface RowMenuConfirmation {
  /** Nom accessible du menu dans son 2e état (la question posée). */
  question: string;
  confirmLabel: string;
  cancelLabel: string;
}

export type RowMenuEntry =
  | {
    key: string; label: string; icon?: ReactNode; onSelect: () => void; danger?: boolean;
    /** `bouton` (défaut) : focus rendu au bouton du menu ; `fenetre` : l'action
     *  ouvre une fenêtre qui prend le focus ; `ligne` : la ligne disparaît. */
    apres?: RowMenuApres;
    /** Demande une confirmation avant `onSelect`. */
    confirmation?: RowMenuConfirmation;
  }
  | { key: string; separator: true };

interface RowMenuProps {
  /** Nom accessible du bouton (« Actions pour … »). */
  label: string;
  entries: RowMenuEntry[];
  /** Classes du bouton déclencheur (en plus de `iconbtn more`). */
  buttonClassName?: string;
  iconSize?: number;
}

/** Évènement interne : un menu s'ouvre, les autres se ferment. */
const OUVERTURE = 'rowmenu:open';

export default function RowMenu({ label, entries, buttonClassName = '', iconSize = 18 }: RowMenuProps) {
  const id = useId();
  const [ouvert, setOuvert] = useState(false);
  const [versLeHaut, setVersLeHaut] = useState(false);
  // Clé de l'entrée en attente de confirmation (2e état du menu), sinon null.
  // On garde la clé, pas l'entrée : son action est relue dans `entries` au
  // moment de valider, jamais une fonction capturée à un rendu ancien.
  const [cleConfirmant, setCleConfirmant] = useState<string | null>(null);
  const confirmant = cleConfirmant === null ? null
    : entries.find((e): e is Extract<RowMenuEntry, { label: string }> =>
      !('separator' in e) && e.key === cleConfirmant) ?? null;
  const idQuestion = `${id}-question`;
  const bouton = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLUListElement>(null);
  // Clé de l'entrée à laquelle rendre le focus après « Annuler ».
  const retour = useRef<string | null>(null);

  const fermer = useCallback((rendreFocus: boolean) => {
    setOuvert(false);
    setVersLeHaut(false);
    setCleConfirmant(null);
    retour.current = null;
    if (rendreFocus) bouton.current?.focus();
  }, []);

  const items = () => Array.from(
    menu.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]') ?? []);

  // Focus sur la première entrée à l'ouverture et à chaque changement d'état ;
  // en revenant de la confirmation, sur l'entrée qui l'avait demandée.
  useEffect(() => {
    if (!ouvert) return;
    const liste = items();
    if (confirmant) { liste[0]?.focus(); return; }
    const cible = retour.current
      ? liste.find(b => b.dataset.cle === retour.current)
      : undefined;
    retour.current = null;
    (cible ?? liste[0])?.focus();
  }, [ouvert, cleConfirmant]);

  // Les entrées changent pendant que le menu est ouvert (l'état du document a
  // bougé) : l'entrée à confirmer a disparu → retour au 1er état ; le focus
  // était sur une entrée retirée → il revient à la première.
  const cles = entries.map(e => e.key).join('|');
  useEffect(() => {
    if (!ouvert) return;
    if (cleConfirmant !== null && !confirmant) { setCleConfirmant(null); return; }
    if (!menu.current?.contains(document.activeElement)) items()[0]?.focus();
  }, [cles]); // eslint-disable-line react-hooks/exhaustive-deps

  // Ouverture vers le haut quand le bas de la liste couperait le menu : il
  // monte depuis le bouton, c'est donc la place au-dessus DU BOUTON qui compte.
  useLayoutEffect(() => {
    if (!ouvert || !menu.current || !bouton.current) return;
    const liste = menu.current.closest('.list');
    if (!liste) return;
    const m = menu.current.getBoundingClientRect();
    const l = liste.getBoundingClientRect();
    const b = bouton.current.getBoundingClientRect();
    if (m.bottom > l.bottom && m.height < b.top - l.top) setVersLeHaut(true);
  }, [ouvert]);

  // Entrée choisie (ou confirmée) : on ferme, on agit, puis on place le focus.
  const valider = (entree: Extract<RowMenuEntry, { label: string }>) => {
    const apres = entree.apres ?? 'bouton';
    // La ligne voisine se repère AVANT l'action : après, elle peut avoir disparu.
    const ligne = bouton.current?.closest('li');
    const voisine = apres === 'ligne'
      ? (ligne?.nextElementSibling ?? ligne?.previousElementSibling ?? null)
      : null;
    const titre = apres === 'ligne'
      ? bouton.current?.closest('section')?.querySelector<HTMLElement>('h2') ?? null
      : null;
    fermer(apres === 'bouton');
    entree.onSelect();
    if (apres === 'ligne') {
      const cible = voisine?.querySelector<HTMLElement>('button:not([disabled])') ?? titre;
      cible?.focus();
    }
  };

  const choisir = (entree: Extract<RowMenuEntry, { label: string }>) => {
    if (entree.confirmation) {
      retour.current = entree.key;
      setCleConfirmant(entree.key);
      return;
    }
    valider(entree);
  };

  // Fermetures extérieures : autre menu, clic ailleurs, Échap.
  useEffect(() => {
    if (!ouvert) return;
    const autreMenu = (e: Event) => { if ((e as CustomEvent).detail !== id) fermer(false); };
    const clic = (e: MouseEvent) => {
      const cible = e.target as Node;
      if (menu.current?.contains(cible) || bouton.current?.contains(cible)) return;
      fermer(false);
    };
    const echap = (e: globalThis.KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      e.stopPropagation();
      fermer(true);
    };
    window.addEventListener(OUVERTURE, autreMenu);
    document.addEventListener('mousedown', clic);
    document.addEventListener('keydown', echap, true);
    return () => {
      window.removeEventListener(OUVERTURE, autreMenu);
      document.removeEventListener('mousedown', clic);
      document.removeEventListener('keydown', echap, true);
    };
  }, [ouvert, id, fermer]);

  const basculer = () => {
    if (ouvert) { fermer(false); return; }
    window.dispatchEvent(new CustomEvent(OUVERTURE, { detail: id }));
    setOuvert(true);
  };

  const surTouche = (e: KeyboardEvent<HTMLUListElement>) => {
    const liste = items();
    const i = liste.indexOf(document.activeElement as HTMLButtonElement);
    if (e.key === 'ArrowDown') { e.preventDefault(); liste[(i + 1) % liste.length]?.focus(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); liste[(i - 1 + liste.length) % liste.length]?.focus(); }
    else if (e.key === 'Home') { e.preventDefault(); liste[0]?.focus(); }
    else if (e.key === 'End') { e.preventDefault(); liste[liste.length - 1]?.focus(); }
    else if (e.key === 'Tab') fermer(false);
  };

  return (
    <>
      <button ref={bouton} type="button"
        className={`iconbtn more ${buttonClassName}`.trim()}
        aria-label={label} aria-haspopup="menu" aria-expanded={ouvert}
        aria-controls={ouvert ? id : undefined}
        onClick={basculer}>
        <MoreHorizontal size={iconSize} strokeWidth={2} aria-hidden="true" />
      </button>
      {ouvert && (
        <ul ref={menu} id={id} role="menu"
          aria-label={confirmant?.confirmation?.question ?? label}
          className={versLeHaut ? 'menu menu--up' : 'menu'}
          onKeyDown={surTouche}>
          {confirmant?.confirmation ? (
            <>
              <li role="none">
                <button type="button" role="menuitem" className="danger" data-cle="confirmer"
                  aria-describedby={idQuestion}
                  onClick={() => valider(confirmant)}>
                  {confirmant.confirmation.confirmLabel}
                </button>
              </li>
              <li role="none">
                <button type="button" role="menuitem" data-cle="annuler"
                  onClick={() => setCleConfirmant(null)}>
                  {confirmant.confirmation.cancelLabel}
                </button>
              </li>
            </>
          ) : entries.map((entree) => 'separator' in entree ? (
            <li key={entree.key} role="separator"><hr /></li>
          ) : (
            <li key={entree.key} role="none">
              <button type="button" role="menuitem" data-cle={entree.key}
                className={entree.danger ? 'danger' : undefined}
                onClick={() => choisir(entree)}>
                {entree.icon}
                {entree.label}
              </button>
            </li>
          ))}
        </ul>
      )}
      {/* Question lue avec « Confirmer » : le nom du menu ne l'est pas toujours. */}
      {ouvert && confirmant?.confirmation && (
        <span id={idQuestion} hidden>{confirmant.confirmation.question}</span>
      )}
    </>
  );
}
