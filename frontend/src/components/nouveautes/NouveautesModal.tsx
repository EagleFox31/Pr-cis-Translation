import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { useNouveautes, type AVoir } from '../../hooks/useNouveautes';
import { subscribeNouveautes, type ModeNouveautes } from './nouveautesBus';
import VisiteAccueil from './VisiteAccueil';
import DepuisModal from './DepuisModal';
import './modal.css';

const CLE_VISITE_INVITE = 'precis.visite_vue';

const FOCUSABLES = 'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Hôte unique des fenêtres « Nouveautés » (visite d'accueil et « depuis votre
 * dernière visite »), ouvert par `openNouveautes`. Fermer = avoir vu.
 */
export default function NouveautesModal() {
  const { i18n } = useTranslation();
  const { user } = useAuth();
  const { chargerAVoir, marquerVu } = useNouveautes();

  const [ouverte, setOuverte] = useState<{ mode: ModeNouveautes; donnees: AVoir | null } | null>(null);
  const origine = useRef<HTMLElement | null>(null);
  const contenant = useRef<HTMLDivElement>(null);
  const enCours = useRef(false);

  // Valeurs courantes lues par l'abonnement au bus, sans le réabonner.
  const courant = useRef({ user, lang: i18n.language, chargerAVoir, ouverte });
  courant.current = { user, lang: i18n.language, chargerAVoir, ouverte };

  useEffect(() => subscribeNouveautes(async (d) => {
    if (enCours.current || courant.current.ouverte) return;
    enCours.current = true;
    try {
      let donnees = d.donnees ?? null;
      if (d.mode === 'depuis' && !donnees) {
        donnees = await courant.current.chargerAVoir(courant.current.lang.startsWith('en') ? 'en' : 'fr');
        // Erreur ou rien de neuf : on n'ouvre rien.
        if (!donnees || donnees.elements.length === 0) return;
      }
      origine.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      setOuverte({ mode: d.mode, donnees });
    } finally {
      enCours.current = false;
    }
  }), []);

  const fermer = useCallback((restaurerFocus = true) => {
    const cible = origine.current;
    setOuverte(null);
    if (restaurerFocus && cible?.isConnected) window.setTimeout(() => cible.focus(), 0);
    // Fermer = avoir vu : compte côté serveur, invité dans le navigateur.
    if (courant.current.user) void marquerVu();
    else {
      try { localStorage.setItem(CLE_VISITE_INVITE, '1'); } catch { /* stockage indisponible */ }
    }
  }, [marquerVu]);

  // Focus sur la fenêtre elle-même à l'ouverture : lecteurs d'écran annoncés,
  // aucun anneau de focus imposé à l'écran ; Tab mène ensuite à la croix.
  useEffect(() => {
    if (!ouverte) return;
    contenant.current?.querySelector<HTMLElement>('[role="dialog"]')?.focus();
  }, [ouverte]);

  // Échap ferme ; Tab reste dans la fenêtre.
  useEffect(() => {
    if (!ouverte) return;
    const touche = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.preventDefault(); fermer(); return; }
      if (e.key !== 'Tab') return;
      const dlg = contenant.current?.querySelector<HTMLElement>('[role="dialog"]');
      if (!dlg) return;
      const liste = Array.from(dlg.querySelectorAll<HTMLElement>(FOCUSABLES)).filter((el) => el.offsetParent !== null);
      if (liste.length === 0) return;
      const premier = liste[0];
      const dernier = liste[liste.length - 1];
      const actif = document.activeElement;
      if (!dlg.contains(actif)) { e.preventDefault(); premier.focus(); }
      else if (actif === dlg) { e.preventDefault(); (e.shiftKey ? dernier : premier).focus(); }
      else if (e.shiftKey && actif === premier) { e.preventDefault(); dernier.focus(); }
      else if (!e.shiftKey && actif === dernier) { e.preventDefault(); premier.focus(); }
    };
    document.addEventListener('keydown', touche);
    return () => document.removeEventListener('keydown', touche);
  }, [ouverte, fermer]);

  if (!ouverte) return null;
  return createPortal(
    <div ref={contenant}>
      <div
        className={`nv-veil${ouverte.mode === 'accueil' ? ' nv-veil--plein' : ''}`}
        onMouseDown={() => fermer()}
        aria-hidden="true"
      />
      {ouverte.mode === 'accueil'
        ? <VisiteAccueil onClose={fermer} />
        : ouverte.donnees && <DepuisModal donnees={ouverte.donnees} onClose={fermer} />}
    </div>,
    document.body,
  );
}
