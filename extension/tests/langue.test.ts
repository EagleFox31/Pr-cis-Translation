import { test } from "node:test";
import assert from "node:assert/strict";
import { langueAProposer, nomLangue } from "../src/lib/langue.ts";

const fiable = (language: string) => ({ isReliable: true, languages: [{ language, percentage: 95 }] });
const douteuse = { isReliable: false, languages: [{ language: "de", percentage: 40 }] };

test("texte trop court : rien à proposer", () => {
  assert.equal(langueAProposer(fiable("en"), "en", "fr", 199), null);
  assert.equal(langueAProposer(fiable("en"), "en", "fr", 200), "en");
});

test("détection fiable : première langue, sans région", () => {
  assert.equal(langueAProposer(fiable("en-US"), "", "fr", 500), "en");
});

test("détection douteuse : repli sur <html lang>, sinon rien", () => {
  assert.equal(langueAProposer(douteuse, "es-MX", "fr", 500), "es");
  assert.equal(langueAProposer(douteuse, "", "fr", 500), null);
});

test("langue inconnue ou identique à la cible : rien", () => {
  assert.equal(langueAProposer(fiable("und"), "", "fr", 500), null);
  assert.equal(langueAProposer(fiable("fr"), "", "fr", 500), null);
  assert.equal(langueAProposer({ isReliable: true, languages: [] }, "", "fr", 500), null);
});

test("nom de langue en français, repli sur le code", () => {
  assert.equal(nomLangue("en"), "anglais");
  assert.equal(nomLangue("xx-invalide-"), "xx-invalide-");
});
