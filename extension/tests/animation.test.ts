import { test } from "node:test";
import assert from "node:assert/strict";
import { DetecteurAnimation } from "../src/lib/animation.ts";

test("trois changements en 2 s : pas animé", () => {
  const d = new DetecteurAnimation();
  assert.equal(d.changement(1, 0), false);
  assert.equal(d.changement(1, 500), false);
  assert.equal(d.changement(1, 1000), false);
  assert.equal(d.estAnime(1), false);
});

test("quatre changements en 2 s : animé", () => {
  const d = new DetecteurAnimation();
  d.changement(1, 0);
  d.changement(1, 400);
  d.changement(1, 800);
  assert.equal(d.changement(1, 1200), true);
  assert.equal(d.estAnime(1), true);
});

test("changements espacés : jamais animé", () => {
  const d = new DetecteurAnimation();
  for (let i = 0; i < 10; i++) assert.equal(d.changement(1, i * 1500), false);
  assert.equal(d.estAnime(1), false);
});

test("un élément animé le reste", () => {
  const d = new DetecteurAnimation();
  for (let t = 0; t < 4; t++) d.changement(1, t * 100);
  assert.equal(d.changement(1, 60000), true);
  assert.equal(d.estAnime(1), true);
});

test("les éléments sont indépendants", () => {
  const d = new DetecteurAnimation();
  for (let t = 0; t < 4; t++) d.changement(1, t * 100);
  d.changement(2, 0);
  assert.equal(d.estAnime(2), false);
});
