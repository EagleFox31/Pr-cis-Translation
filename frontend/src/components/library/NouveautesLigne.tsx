/**
 * Ligne « Nouveautés » du panneau de compte, entre le solde et « Mes documents ».
 *
 * À gauche, l'entrée : la pastille compte ce qui reste à voir ; un clic rouvre
 * la fenêtre « depuis votre dernière visite » (tiroir fermé d'abord), ou mène
 * à la page Fonctionnalités quand il n'y a rien de neuf.
 * À droite, l'interrupteur « E-mail » : bascule immédiate, retour à l'état
 * précédent si le serveur refuse (le message d'erreur vient du hook).
 */
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { ChevronRight, Mail, Sparkles } from 'lucide-react';

import type { AuthUser } from '../../contexts/AuthContext';
import { useNouveautes, type AVoir } from '../../hooks/useNouveautes';
import { openNouveautes } from '../nouveautes/nouveautesBus';
import './nouveautes-ligne.css';

interface Props {
  user: AuthUser;
  /** Ferme le tiroir avant d'ouvrir la fenêtre ou de changer de page. */
  onClose: () => void;
}

export default function NouveautesLigne({ user, onClose }: Props) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { chargerAVoir, setAbonnement } = useNouveautes();
  const langue = i18n.language?.startsWith('en') ? 'en' : 'fr';
  const [aVoir, setAVoir] = useState<AVoir | null>(null);
  const [abonne, setAbonne] = useState(!!user.abonne_nouveautes);
  const [envoi, setEnvoi] = useState(false);

  useEffect(() => { setAbonne(!!user.abonne_nouveautes); }, [user.abonne_nouveautes]);

  // Relu quand la date « vu » change : fermer la fenêtre vide la pastille.
  useEffect(() => {
    let vivant = true;
    chargerAVoir(langue).then(d => { if (vivant) setAVoir(d); });
    return () => { vivant = false; };
  }, [chargerAVoir, langue, user.nouveautes_vues_le]);

  const nombre = aVoir?.elements.length ?? 0;

  const ouvrir = () => {
    onClose();
    if (aVoir && nombre > 0) {
      openNouveautes(aVoir.mode === 'accueil' ? 'accueil' : 'depuis', aVoir);
    } else {
      navigate('/fonctionnalites');
    }
  };

  const basculer = async () => {
    if (envoi) return;
    const avant = abonne;
    setAbonne(!avant);
    setEnvoi(true);
    const ok = await setAbonnement(!avant);
    if (!ok) setAbonne(avant);
    setEnvoi(false);
  };

  return (
    <div className="news">
      <button type="button" className="news__entree" onClick={ouvrir}>
        <Sparkles size={18} className="news__ic" aria-hidden="true" />
        {t('nouveautes.panel.title')}
        {nombre > 0 && (
          <span className="news__cnt" aria-label={t('nouveautes.panel.count', { count: nombre })}>
            {nombre}
          </span>
        )}
        <ChevronRight size={16} className="news__chev" aria-hidden="true" />
      </button>
      <button type="button" className="news__mail" role="switch" aria-checked={abonne}
        aria-label={t('nouveautes.subscribe.label')} disabled={envoi} onClick={basculer}>
        <Mail size={14} aria-hidden="true" />
        <span>{t('nouveautes.panel.email')}</span>
        <span className="ui-switch ui-switch--sm" aria-hidden="true" />
      </button>
    </div>
  );
}
