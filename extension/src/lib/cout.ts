/** Accord avant de traduire des images : l'extension ne coûte aucun crédit, on annonce seulement le nombre. */
export function messageAccord(nbImages: number): string {
  return `${nbImages} image${nbImages > 1 ? "s" : ""} à traduire`;
}

/** Budget d'images de la page épuisé : seules les images à texte traduites l'ont consommé. */
export function messageLimiteImages(traduites: number, vues: number): string {
  return `${traduites} image${traduites > 1 ? "s" : ""} sur ${vues} traduite${traduites > 1 ? "s" : ""} — limite atteinte pour cette page`;
}
