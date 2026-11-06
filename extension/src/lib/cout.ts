export function messageAccord(nbImages: number): string {
  const pluriel = nbImages > 1;
  return (
    `${nbImages} image${pluriel ? "s" : ""} avec du texte possible — ` +
    `jusqu'à ${nbImages} crédit${pluriel ? "s" : ""} (débit seulement si l'image est traduite)`
  );
}
