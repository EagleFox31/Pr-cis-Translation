import { test } from "node:test";
import assert from "node:assert/strict";
import {
  aEnvoyer,
  aEvincer,
  BORNES,
  cleImage,
  cleTexte,
  empreinte,
  empreinteCompte,
  libelleMemoire,
  Memoire,
} from "../src/lib/memoire.ts";
import type { EntreeMemoire, Genre, Magasin, Meta } from "../src/lib/memoire.ts";

const JOUR = 24 * 60 * 60 * 1000;

class MagasinTest implements Magasin {
  lignes: Record<Genre, Map<string, EntreeMemoire & { utilise: number }>> = { textes: new Map(), images: new Map() };
  panne = false;

  async lire(genre: Genre, cles: string[], maintenant: number) {
    if (this.panne) throw new Error("panne");
    const trouves = new Map<string, unknown>();
    for (const cle of cles) {
      const ligne = this.lignes[genre].get(cle);
      if (!ligne) continue;
      trouves.set(cle, ligne.valeur);
      ligne.utilise = maintenant;
    }
    return trouves;
  }
  async ecrire(genre: Genre, entrees: EntreeMemoire[], maintenant: number) {
    if (this.panne) throw new Error("panne");
    for (const e of entrees) this.lignes[genre].set(e.cle, { ...e, utilise: maintenant });
  }
  async metas(genre: Genre): Promise<Meta[]> {
    return [...this.lignes[genre].values()].map(({ cle, utilise, taille }) => ({ cle, utilise, taille }));
  }
  async supprimer(genre: Genre, cles: string[]) {
    for (const cle of cles) this.lignes[genre].delete(cle);
  }
  async compter(compte: string) {
    return [...this.lignes.textes.values(), ...this.lignes.images.values()].filter((l) => l.compte === compte).length;
  }
  async effacer(compte: string) {
    for (const table of Object.values(this.lignes)) {
      for (const [cle, ligne] of table) if (ligne.compte === compte) table.delete(cle);
    }
  }
}

test("empreinte : le découpage des parties compte", async () => {
  assert.notEqual(await empreinte("ab", "c"), await empreinte("a", "bc"));
  assert.match(await empreinte("x"), /^[0-9a-f]{64}$/);
});

test("clés : séparées par compte, langue et contenu", async () => {
  const base = await cleTexte("a", "fr", "Hello");
  assert.equal(base, await cleTexte("a", "fr", "Hello"));
  assert.notEqual(base, await cleTexte("b", "fr", "Hello"));
  assert.notEqual(base, await cleTexte("a", "es", "Hello"));
  assert.notEqual(base, await cleTexte("a", "fr", "Hello!"));
});

test("clé d'image : dépend des octets, pas de l'adresse", async () => {
  const a = new Uint8Array([1, 2, 3]);
  assert.equal(await cleImage("a", "fr", a), await cleImage("a", "fr", new Uint8Array([1, 2, 3])));
  assert.notEqual(await cleImage("a", "fr", a), await cleImage("a", "fr", new Uint8Array([1, 2, 4])));
});

test("compte : même adresse quelle que soit la casse, jamais en clair", async () => {
  const c = await empreinteCompte(" A@Example.com ");
  assert.equal(c, await empreinteCompte("a@example.com"));
  assert.ok(!c.includes("example"));
});

test("aEnvoyer : seulement l'inconnu, une seule fois", () => {
  const connus = new Map([["a", "A"]]);
  assert.deepEqual(aEnvoyer(["a", "b", "b", "c"], connus), ["b", "c"]);
  assert.deepEqual(aEnvoyer(["a", "a"], connus), []);
});

test("aEvincer : l'âge limite retire les entrées vieilles de plus de 30 jours", () => {
  const maintenant = 100 * JOUR;
  const metas = [
    { cle: "vieille", utilise: maintenant - 31 * JOUR, taille: 1 },
    { cle: "limite", utilise: maintenant - 30 * JOUR, taille: 1 },
    { cle: "recente", utilise: maintenant, taille: 1 },
  ];
  assert.deepEqual(aEvincer(metas, BORNES.textes, maintenant), ["vieille"]);
});

test("aEvincer : au-delà du nombre maximal, les moins récentes partent d'abord", () => {
  const metas = [3, 1, 2].map((u) => ({ cle: `k${u}`, utilise: u, taille: 1 }));
  assert.deepEqual(aEvincer(metas, { ageMaxMs: JOUR, entreesMax: 2 }, 3), ["k1"]);
});

test("aEvincer : au-delà du volume maximal, retire jusqu'à repasser sous la borne", () => {
  const metas = [1, 2, 3].map((u) => ({ cle: `k${u}`, utilise: u, taille: 100 }));
  assert.deepEqual(aEvincer(metas, { ageMaxMs: JOUR, octetsMax: 150 }, 3), ["k1", "k2"]);
  assert.deepEqual(aEvincer(metas, { ageMaxMs: JOUR, octetsMax: 300 }, 3), []);
});

test("libellé : vide, singulier, pluriel", () => {
  assert.equal(libelleMemoire(0), "Mémoire : vide");
  assert.equal(libelleMemoire(1), "Mémoire : 1 traduction");
  assert.equal(libelleMemoire(2), "Mémoire : 2 traductions");
});

test("textes : relus à l'identique, sans fuite vers un autre compte ni une autre langue", async () => {
  const m = new Memoire(new MagasinTest());
  await m.garderTextes("a", "fr", ["Hello"], ["Bonjour"]);
  assert.equal((await m.lireTextes("a", "fr", ["Hello", "Hello", "New"])).get("Hello"), "Bonjour");
  assert.equal((await m.lireTextes("b", "fr", ["Hello"])).size, 0);
  assert.equal((await m.lireTextes("a", "es", ["Hello"])).size, 0);
});

test("textes : une réponse égale à l'original n'est pas gardée", async () => {
  const m = new Memoire(new MagasinTest());
  await m.garderTextes("a", "fr", ["Same", "Hello"], ["Same", "Bonjour"]);
  const connus = await m.lireTextes("a", "fr", ["Same", "Hello"]);
  assert.equal(connus.has("Same"), false);
  assert.equal(connus.get("Hello"), "Bonjour");
});

test("image : une réponse sans remplacement se relit aussi", async () => {
  const m = new Memoire(new MagasinTest());
  await m.garderImage("cle", "a", { remplacee: false, image: null }, 10);
  assert.deepEqual(await m.lireImage("cle"), { remplacee: false, image: null });
  assert.equal(await m.lireImage("autre"), null);
});

test("panne de la base : rien de connu, aucune exception", async () => {
  const magasin = new MagasinTest();
  const m = new Memoire(magasin);
  magasin.panne = true;
  await m.garderTextes("a", "fr", ["Hello"], ["Bonjour"]);
  await m.garderImage("cle", "a", {}, 1);
  assert.equal((await m.lireTextes("a", "fr", ["Hello"])).size, 0);
  assert.equal(await m.lireImage("cle"), null);
});

test("purge : déclenchée à l'écriture, au plus une fois par minute", async () => {
  const magasin = new MagasinTest();
  let maintenant = 40 * JOUR;
  const m = new Memoire(magasin, () => maintenant);
  await m.garderImage("ancienne", "a", {}, 1);
  maintenant += 31 * JOUR;
  await m.garderImage("nouvelle", "a", {}, 1);
  assert.deepEqual([...magasin.lignes.images.keys()], ["nouvelle"]);

  await m.garderImage("autre", "a", {}, 1);
  magasin.lignes.images.get("nouvelle")!.utilise = 0;
  await m.garderImage("encore", "a", {}, 1);
  assert.ok(magasin.lignes.images.has("nouvelle"), "pas de deuxième purge dans la même minute");
});

test("compter et effacer : limités au compte", async () => {
  const m = new Memoire(new MagasinTest());
  await m.garderTextes("a", "fr", ["x", "y"], ["X", "Y"]);
  await m.garderImage("img", "a", {}, 1);
  await m.garderTextes("b", "fr", ["x"], ["X"]);
  assert.equal(await m.compter("a"), 3);
  await m.effacer("a");
  assert.equal(await m.compter("a"), 0);
  assert.equal(await m.compter("b"), 1);
});
