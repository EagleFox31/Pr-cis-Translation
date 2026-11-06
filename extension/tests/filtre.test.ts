import { test } from "node:test";
import assert from "node:assert/strict";
import { aTraduire } from "../src/lib/filtre.ts";

test("rejette le vide et les espaces", () => {
  assert.equal(aTraduire(""), false);
  assert.equal(aTraduire("  \n\t "), false);
});

test("rejette les textes sans lettre", () => {
  assert.equal(aTraduire("12345"), false);
  assert.equal(aTraduire("12,5 %"), false);
  assert.equal(aTraduire("— / ... !"), false);
});

test("rejette une seule lettre", () => {
  assert.equal(aTraduire("a"), false);
  assert.equal(aTraduire(" A. "), false);
  assert.equal(aTraduire("1 x"), false);
});

test("accepte du vrai texte", () => {
  assert.equal(aTraduire("Bonjour"), true);
  assert.equal(aTraduire("ok"), true);
  assert.equal(aTraduire("Page 2"), true);
  assert.equal(aTraduire("été"), true);
  assert.equal(aTraduire("مرحبا"), true);
});
