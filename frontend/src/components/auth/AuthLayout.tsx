/**
 * Le cadre commun des pages d'authentification : fond, carte, marque.
 *
 * `LoginPage` et `RegisterPage` en portaient chacune leur copie — mêmes sept
 * constantes de style (`pageStyle`, `cardStyle`, `inputBase`, `btnPrimary`,
 * `digitBase`, `logoStyle`, et les deux gestionnaires de focus), au caractère
 * près. `logoStyle` n'était d'ailleurs utilisé NI dans l'une NI dans l'autre.
 *
 * LA MARQUE N'APPARAÎT QU'UNE FOIS
 * --------------------------------
 * L'en-tête affichait DEUX logos côte à côte : le « P » animé avec le mot
 * « récis » à gauche, et l'image d'identité à droite. La même marque, écrite
 * deux fois, sur 48 pixels de hauteur — dans un formulaire que l'on reprochait
 * déjà d'être trop long.
 */
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Loader2 } from 'lucide-react';

import AuthBackground from './AuthBackground';

interface AuthLayoutProps {
  /** Lien ou bouton de retour, affiché au-dessus du titre. */
  retour?: { label: string; to?: string; onClick?: () => void };
  /** Voile d'attente couvrant la carte (retour de Google, par exemple). */
  attente?: string | null;
  children: ReactNode;
}

export default function AuthLayout({ retour, attente, children }: AuthLayoutProps) {
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

        <img src="/Identite Precis.png" alt="Précis" className="auth-marque" />

        {retour && (
          retour.to
            ? <Link to={retour.to} className="auth-retour">
                <ArrowLeft size={14} aria-hidden /> {retour.label}
              </Link>
            : <button type="button" className="auth-retour" onClick={retour.onClick}>
                <ArrowLeft size={14} aria-hidden /> {retour.label}
              </button>
        )}

        {children}
      </div>
    </div>
  );
}
