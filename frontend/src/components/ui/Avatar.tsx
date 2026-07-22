/**
 * Pastille d'initiale. La couleur est DÉRIVÉE du nom : deux comptes différents
 * n'ont pas la même, et le même compte garde la sienne d'une session à l'autre.
 *
 * Un avatar toujours bleu identifie l'application, pas la personne.
 */
interface AvatarProps {
  name?: string | null;
  email?: string | null;
  size?: number;
}

/** Teintes lisibles sur texte blanc — pas de jaune ni de vert clair. */
const TEINTES = [212, 258, 280, 330, 8, 24, 160, 190];

export default function Avatar({ name, email, size = 44 }: AvatarProps) {
  const source = (name || email || '?').trim();
  const initiale = source[0]?.toUpperCase() ?? '?';

  // Somme des codes de caractères : stable, et suffisante pour répartir.
  let somme = 0;
  for (let i = 0; i < source.length; i++) somme += source.charCodeAt(i);
  const teinte = TEINTES[somme % TEINTES.length];

  return (
    <span
      className="ui-avatar"
      style={{
        width: size, height: size, fontSize: size * 0.4,
        background: `linear-gradient(140deg, hsl(${teinte} 72% 52%), hsl(${teinte + 18} 68% 42%))`,
      }}
      aria-hidden
    >
      {initiale}
    </span>
  );
}
