import { test } from "node:test";
import assert from "node:assert/strict";
import { enParallele } from "../src/lib/parallele.ts";

const attendre = (ms: number) => new Promise((r) => setTimeout(r, ms));

test("au plus n traitements à la fois, tous les éléments traités", async () => {
  const file = [1, 2, 3, 4, 5];
  let actifs = 0;
  let pic = 0;
  const faits: number[] = [];
  await enParallele(2, () => file.shift(), async (x) => {
    pic = Math.max(pic, ++actifs);
    await attendre(5);
    actifs--;
    faits.push(x);
    return false;
  });
  assert.equal(pic, 2);
  assert.deepEqual(faits.sort(), [1, 2, 3, 4, 5]);
});

test("un arrêt laisse finir l'élément en cours et n'en prend plus", async () => {
  const file = [1, 2, 3, 4, 5, 6];
  const faits: number[] = [];
  await enParallele(2, () => file.shift(), async (x) => {
    await attendre(x === 1 ? 1 : 10);
    faits.push(x);
    return x === 1;
  });
  assert.deepEqual(faits.sort(), [1, 2]);
  assert.deepEqual(file, [3, 4, 5, 6]);
});

test("file vide : rien n'est traité", async () => {
  let appels = 0;
  await enParallele(3, () => undefined, async () => (appels++, false));
  assert.equal(appels, 0);
});

test("une exception arrête tous les travailleurs et remonte", async () => {
  const file = [1, 2, 3, 4, 5, 6];
  const faits: number[] = [];
  await assert.rejects(
    enParallele(2, () => file.shift(), async (x) => {
      if (x === 1) throw new Error("panne");
      await attendre(10);
      faits.push(x);
      return false;
    }),
    /panne/,
  );
  await attendre(30);
  assert.deepEqual(faits, [2]);
  assert.deepEqual(file, [3, 4, 5, 6]);
});
