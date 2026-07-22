/**
 * Le cadre commun des pages d'authentification : fond, carte, marque, titre.
 *
 * `LoginPage` et `RegisterPage` en portaient chacune leur copie — mêmes sept
 * constantes de style (`pageStyle`, `cardStyle`, `inputBase`, `btnPrimary`,
 * `digitBase`, `logoStyle`, et les deux gestionnaires de focus), au caractère
 * près. `logoStyle` n'était d'ailleurs utilisé NI dans l'une NI dans l'autre.
 *
 * L'EN-TÊTE DE MARQUE
 * -------------------
 * Le « P » et le mot « récis » à gauche, l'identité à droite. J'avais fondu les
 * deux en une seule image pour raccourcir l'écran : c'était retirer la signature
 * visuelle du produit pour gagner quelques pixels. Les deux sont revenues.
 *
 * Le gain de hauteur, lui, vient d'ailleurs : le retour et le titre partagent
 * une SEULE ligne au lieu de s'empiler.
 */
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Loader2 } from 'lucide-react';

import AuthBackground from './AuthBackground';

interface AuthLayoutProps {
  /** Lien ou bouton de retour — sur la même ligne que le titre. */
  retour?: { label: string; to?: string; onClick?: () => void };
  /** Titre de l'écran. Absent sur les étapes qui portent le leur (`CodeStep`). */
  titre?: string;
  sousTitre?: string;
  /** Voile d'attente couvrant la carte (retour de Google, par exemple). */
  attente?: string | null;
  children: ReactNode;
}

export default function AuthLayout({
  retour, titre, sousTitre, attente, children,
}: AuthLayoutProps) {
  // Le retour est un bouton ROND, sans son libellé.
  //
  // Deux dispositions ont échoué avant celle-ci. Le libellé posé à gauche d'un
  // titre centré laissait un bord droit vide : un élément à gauche, un au
  // centre, rien en face — et le déséquilibre CHANGEAIT avec la langue, puisque
  // « Accueil » et « Home » n'ont pas la même longueur.
  //
  // Réduit à sa flèche, le retour forme un seul bloc avec le titre, aligné à
  // gauche. Plus rien ne flotte, et la mise en page ne dépend plus des mots.
  // Le libellé n'est pas perdu : il reste le nom accessible du bouton et son
  // infobulle — annoncé par un lecteur d'écran, lisible au survol.
  //
  // Les classes sont celles de `ui/IconButton` : même apparence, même état de
  // focus, une seule définition. Un `<Link>` ne peut pas être ce composant
  // (c'est un `<button>`), mais il peut en porter l'habit.
  const CLASSES_RETOUR = 'ui-iconbtn ui-iconbtn--ghost ui-iconbtn--md auth-retour';
  const lienRetour = retour && (
    retour.to
      ? <Link to={retour.to} className={CLASSES_RETOUR}
              aria-label={retour.label} title={retour.label}>
          <ArrowLeft size={16} aria-hidden />
        </Link>
      : <button type="button" className={CLASSES_RETOUR} onClick={retour.onClick}
                aria-label={retour.label} title={retour.label}>
          <ArrowLeft size={16} aria-hidden />
        </button>
  );

  return (
    <div className="auth-page">
      <AuthBackground />
      <div className="auth-carte">
        {attente && (
          <div className="auth-carte__voile">
            <Loader2 size={28} className="ui-spin" aria-hidden />
            <span>{attente}</span>
          </div>
        )}

        <header className="auth-marque">
          <span className="auth-marque__nom">
            <img src="/Logo.png" alt="P" className="auth-marque__logo" />
            <span className="animated-logo-text">récis</span>
          </span>
          {/* `alt` vide : la marque vient d'être annoncée par « P » + « récis ».
              La répéter ferait dire « Précis Précis » à un lecteur d'écran. */}
          <img src="/Identite Precis.png" alt="" className="auth-marque__identite" />
        </header>

        {(lienRetour || titre) && (
          <div className="auth-ligne-titre">
            {lienRetour}
            {titre && <h1 className="auth-titre">{titre}</h1>}
          </div>
        )}
        {sousTitre && <p className="auth-sous-titre">{sousTitre}</p>}

        {children}
      </div>
    </div>
  );
}
