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
  const lienRetour = retour && (
    retour.to
      ? <Link to={retour.to} className="auth-retour">
          <ArrowLeft size={14} aria-hidden /> {retour.label}
        </Link>
      : <button type="button" className="auth-retour" onClick={retour.onClick}>
          <ArrowLeft size={14} aria-hidden /> {retour.label}
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
