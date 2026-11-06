export function messageAccord(nbImages: number): string {
  const pluriel = nbImages > 1;
  return (
    `${nbImages} image${pluriel ? "s" : ""} avec du texte possible — ` +
    `jusqu'à ${nbImages} crédit${pluriel ? "s" : ""} (débit seulement si l'image est traduite)`
  );
}

/** Budget d'images de la page épuisé : seules les images à texte traduites l'ont consommé. */
export function messageLimiteImages(traduites: number, vues: number): string {
  return `${traduites} image${traduites > 1 ? "s" : ""} sur ${vues} traduite${traduites > 1 ? "s" : ""} — limite atteinte pour cette page`;
}
