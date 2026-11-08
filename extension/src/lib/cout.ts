export function messageAccord(nbImages: number): string {
  const pluriel = nbImages > 1;
  // Seules les images analysées comme traduisibles sont comptées ; celles déjà
  // traduites pour ce compte ne sont pas redébitées, d'où « jusqu'à ».
  return `${nbImages} image${pluriel ? "s" : ""} à traduire — jusqu'à ${nbImages} crédit${pluriel ? "s" : ""}`;
}

/** Budget d'images de la page épuisé : seules les images à texte traduites l'ont consommé. */
export function messageLimiteImages(traduites: number, vues: number): string {
  return `${traduites} image${traduites > 1 ? "s" : ""} sur ${vues} traduite${traduites > 1 ? "s" : ""} — limite atteinte pour cette page`;
}
