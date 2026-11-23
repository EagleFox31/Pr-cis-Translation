// Faux pour le vide, les textes sans lettre (nombres, ponctuation) et ceux d'une seule lettre.
export function aTraduire(texte: string): boolean {
  if (texte.trim() === "") return false;
  const lettres = texte.match(/\p{L}/gu);
  return lettres !== null && lettres.length > 1;
}
