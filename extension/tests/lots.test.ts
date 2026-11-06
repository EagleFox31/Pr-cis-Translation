import { test } from "node:test";
import assert from "node:assert/strict";
import { decouperEnLots } from "../src/lib/lots.ts";

test("liste vide : aucun lot", () => {
  assert.deepEqual(decouperEnLots([]), []);
});

test("respecte le nombre maximal de segments", () => {
  const textes = Array.from({ length: 650 }, (_, i) => `t${i}`);
  const lots = decouperEnLots(textes);
  assert.deepEqual(lots.map((l) => l.length), [300, 300, 50]);
  assert.deepEqual(lots.flat(), textes);
});

test("respecte le nombre maximal de caractères", () => {
  const textes = ["a".repeat(10000), "b".repeat(8000), "c".repeat(100)];
  const lots = decouperEnLots(textes);
  assert.equal(lots.length, 2);
  assert.deepEqual(lots[0], [textes[0], textes[1]]);
  assert.deepEqual(lots[1], [textes[2]]);
  for (const lot of lots) assert.ok(lot.join("").length <= 18000);
});

test("un texte trop long est tronqué sans changer le nombre de segments", () => {
  const plat = decouperEnLots(["x".repeat(25000), "fin"]).flat();
  assert.equal(plat.length, 2);
  assert.equal(plat[0]?.length, 18000);
  assert.equal(plat[1], "fin");
});

test("limites personnalisées", () => {
  assert.deepEqual(decouperEnLots(["aa", "bb", "cc"], 2, 100), [["aa", "bb"], ["cc"]]);
});
