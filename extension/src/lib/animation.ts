// Repère les images dont la source change en boucle (animations, carrousels) pour ne pas les traduire.
export class DetecteurAnimation {
  private readonly changements = new Map<number, number[]>();
  private readonly animes = new Set<number>();
  private readonly maxChangements: number;
  private readonly fenetreMs: number;

  constructor(maxChangements = 3, fenetreMs = 2000) {
    this.maxChangements = maxChangements;
    this.fenetreMs = fenetreMs;
  }

  changement(id: number, tMs: number): boolean {
    if (this.animes.has(id)) return true;
    const recents = (this.changements.get(id) ?? []).filter((t) => tMs - t <= this.fenetreMs);
    recents.push(tMs);
    this.changements.set(id, recents);
    if (recents.length > this.maxChangements) {
      this.animes.add(id);
      this.changements.delete(id);
      return true;
    }
    return false;
  }

  estAnime(id: number): boolean {
    return this.animes.has(id);
  }
}
