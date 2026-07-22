/**
 * Saisie d'un code à six chiffres.
 *
 * Le widget existait DEUX fois — `LoginPage` avec des attributs `data-ci`,
 * `RegisterPage` avec des `data-ri`, sinon identiques. Les deux allaient
 * chercher le champ voisin par `document.querySelector` : une recherche dans
 * TOUT le document pour atteindre son propre frère. Deux instances à l'écran
 * (ce qui n'arrive pas aujourd'hui, mais rien ne l'empêchait) et le focus
 * partait dans l'autre.
 *
 * Ici les champs sont tenus par des `ref`. Plus de sélecteur global, plus de
 * jeu d'attributs à ne pas confondre.
 */
import { useRef } from 'react';
import type { ClipboardEvent, KeyboardEvent } from 'react';

interface CodeInputProps {
  value: string[];
  onChange: (code: string[]) => void;
  /** Nom accessible du groupe — « Code de vérification ». */
  label: string;
  autoFocus?: boolean;
}

const TAILLE = 6;

export default function CodeInput({ value, onChange, label, autoFocus }: CodeInputProps) {
  const champs = useRef<(HTMLInputElement | null)[]>([]);

  function saisir(i: number, v: string) {
    if (!/^\d?$/.test(v)) return;
    const suivant = [...value];
    suivant[i] = v;
    onChange(suivant);
    if (v && i < TAILLE - 1) champs.current[i + 1]?.focus();
  }

  function coller(e: ClipboardEvent) {
    const chiffres = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, TAILLE);
    if (chiffres.length !== TAILLE) return;
    e.preventDefault();
    onChange(chiffres.split(''));
    champs.current[TAILLE - 1]?.focus();
  }

  function touche(i: number, e: KeyboardEvent) {
    // Retour arrière sur un champ VIDE : on remonte au précédent. Sans cela,
    // effacer un code déjà saisi demandait de cliquer champ par champ.
    if (e.key === 'Backspace' && !value[i] && i > 0) champs.current[i - 1]?.focus();
    if (e.key === 'ArrowLeft' && i > 0) champs.current[i - 1]?.focus();
    if (e.key === 'ArrowRight' && i < TAILLE - 1) champs.current[i + 1]?.focus();
  }

  return (
    <div className="code" onPaste={coller} role="group" aria-label={label}>
      {Array.from({ length: TAILLE }, (_, i) => (
        <input
          key={i}
          ref={(el) => { champs.current[i] = el; }}
          className="code__chiffre"
          type="text"
          inputMode="numeric"
          autoComplete={i === 0 ? 'one-time-code' : 'off'}
          maxLength={1}
          value={value[i] ?? ''}
          aria-label={`${label} — ${i + 1}/${TAILLE}`}
          onChange={(e) => saisir(i, e.target.value)}
          onKeyDown={(e) => touche(i, e)}
          onFocus={(e) => e.target.select()}
          autoFocus={autoFocus && i === 0}
        />
      ))}
    </div>
  );
}
