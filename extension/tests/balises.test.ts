import { test } from "node:test";
import assert from "node:assert/strict";
import { aDesBalises, analyser, conforme, sansBalises } from "../src/lib/balises.ts";

test("analyse les balises imbriquées", () => {
  assert.deepEqual(analyser("Le [[1]]moteur [[2]]neuf[[/2]][[/1]] tourne"), [
    "Le ",
    { n: 1, enfants: ["moteur ", { n: 2, enfants: ["neuf"] }] },
    " tourne",
  ]);
  assert.deepEqual(analyser("sans balise"), ["sans balise"]);
  assert.deepEqual(analyser("[[3]][[/3]]"), [{ n: 3, enfants: [] }]);
});

test("refuse les balises orphelines, croisées ou répétées", () => {
  assert.equal(analyser("a [[1]]b"), null);
  assert.equal(analyser("a b[[/1]]"), null);
  assert.equal(analyser("[[1]]a[[2]]b[[/1]]c[[/2]]"), null);
  assert.equal(analyser("[[1]]a[[/1]] [[1]]b[[/1]]"), null);
});

test("conforme : mêmes éléments, mêmes parents, vides sans texte", () => {
  const parents = new Map([[1, 0], [2, 1], [3, 0]]);
  const vides = new Set([3]);
  const ok = analyser("[[3]][[/3]] The [[1]]new [[2]]engine[[/2]][[/1]] runs")!;
  assert.equal(conforme(ok, parents, vides), true);
  assert.equal(conforme(analyser("The [[1]]new[[/1]] [[2]]engine[[/2]] [[3]][[/3]]")!, parents, vides), false);
  assert.equal(conforme(analyser("The [[1]]new [[2]]engine[[/2]][[/1]]")!, parents, vides), false);
  assert.equal(conforme(analyser("[[3]]img[[/3]] [[1]]a [[2]]b[[/2]][[/1]]")!, parents, vides), false);
  assert.equal(conforme(analyser("[[3]] [[/3]][[1]]a [[2]]b[[/2]][[/1]]")!, parents, vides), true);
  assert.equal(conforme(analyser("[[4]]x[[/4]][[3]][[/3]][[1]][[2]]b[[/2]][[/1]]")!, parents, vides), false);
});

test("repère et retire les balises", () => {
  assert.equal(aDesBalises("a [[12]]b[[/12]]"), true);
  assert.equal(aDesBalises("a [[b]] c"), false);
  assert.equal(sansBalises("a [[1]]b[[/1]] c"), "a b c");
});
