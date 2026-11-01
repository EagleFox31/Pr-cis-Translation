// Découpe en lots respectant les limites de l'API (300 segments, 20 000 caractères).
// Un texte isolé plus long que la limite est tronqué : l'ordre et le nombre de segments restent identiques.
export function decouperEnLots(
  textes: string[],
  maxSegments = 300,
  maxCaracteres = 18000,
): string[][] {
  const lots: string[][] = [];
  let courant: string[] = [];
  let taille = 0;

  for (const brut of textes) {
    const texte = brut.length > maxCaracteres ? brut.slice(0, maxCaracteres) : brut;
    if (courant.length > 0 && (courant.length >= maxSegments || taille + texte.length > maxCaracteres)) {
      lots.push(courant);
      courant = [];
      taille = 0;
    }
    courant.push(texte);
    taille += texte.length;
  }
  if (courant.length > 0) lots.push(courant);
  return lots;
}
