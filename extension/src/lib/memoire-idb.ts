import type { EntreeMemoire, Genre, Magasin, Meta } from "./memoire.ts";

const BASE = "precis-memoire";
const GENRES: Genre[] = ["textes", "images"];

interface Ligne extends EntreeMemoire {
  utilise: number;
}

function ouvrir(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const demande = indexedDB.open(BASE, 1);
    demande.onupgradeneeded = () => {
      for (const genre of GENRES) {
        const table = demande.result.createObjectStore(genre, { keyPath: "cle" });
        table.createIndex("compte", "compte");
        // Index composé : le tri et la taille se lisent sans charger les images.
        table.createIndex("usage", ["utilise", "taille"]);
      }
    };
    demande.onsuccess = () => resolve(demande.result);
    demande.onerror = () => reject(demande.error);
  });
}

function fin(tx: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error);
  });
}

export class MagasinIndexedDB implements Magasin {
  // Le service de fond peut être arrêté à tout moment : la base se rouvre à la demande.
  private base: Promise<IDBDatabase> | null = null;

  private connexion(): Promise<IDBDatabase> {
    this.base ??= ouvrir().catch((e) => {
      this.base = null;
      throw e;
    });
    return this.base;
  }

  async lire(genre: Genre, cles: string[], maintenant: number): Promise<Map<string, unknown>> {
    const trouves = new Map<string, unknown>();
    if (!cles.length) return trouves;
    const tx = (await this.connexion()).transaction(genre, "readwrite");
    const table = tx.objectStore(genre);
    for (const cle of cles) {
      const demande = table.get(cle);
      demande.onsuccess = () => {
        const ligne = demande.result as Ligne | undefined;
        if (!ligne) return;
        trouves.set(cle, ligne.valeur);
        table.put({ ...ligne, utilise: maintenant });
      };
    }
    await fin(tx);
    return trouves;
  }

  async ecrire(genre: Genre, entrees: EntreeMemoire[], maintenant: number): Promise<void> {
    const tx = (await this.connexion()).transaction(genre, "readwrite");
    const table = tx.objectStore(genre);
    for (const entree of entrees) table.put({ ...entree, utilise: maintenant });
    await fin(tx);
  }

  async metas(genre: Genre): Promise<Meta[]> {
    const tx = (await this.connexion()).transaction(genre, "readonly");
    const metas: Meta[] = [];
    const curseur = tx.objectStore(genre).index("usage").openKeyCursor();
    curseur.onsuccess = () => {
      const c = curseur.result;
      if (!c) return;
      const [utilise, taille] = c.key as [number, number];
      metas.push({ cle: c.primaryKey as string, utilise, taille });
      c.continue();
    };
    await fin(tx);
    return metas;
  }

  async supprimer(genre: Genre, cles: string[]): Promise<void> {
    const tx = (await this.connexion()).transaction(genre, "readwrite");
    const table = tx.objectStore(genre);
    for (const cle of cles) table.delete(cle);
    await fin(tx);
  }

  async compter(compte: string): Promise<number> {
    const tx = (await this.connexion()).transaction(GENRES, "readonly");
    const comptes = GENRES.map((g) => tx.objectStore(g).index("compte").count(compte));
    await fin(tx);
    return comptes.reduce((n, d) => n + d.result, 0);
  }

  async effacer(compte: string): Promise<void> {
    const tx = (await this.connexion()).transaction(GENRES, "readwrite");
    for (const genre of GENRES) {
      const table = tx.objectStore(genre);
      const curseur = table.index("compte").openKeyCursor(compte);
      curseur.onsuccess = () => {
        const c = curseur.result;
        if (!c) return;
        table.delete(c.primaryKey);
        c.continue();
      };
    }
    await fin(tx);
  }
}
