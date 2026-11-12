import { test } from "node:test";
import assert from "node:assert/strict";
import { decision, langueParDefaut, origineDe, resteSuivi } from "../src/lib/suivi.ts";

test("origine http(s) seulement", () => {
  assert.equal(origineDe("https://a.test/x/page1.html?q=1"), "https://a.test");
  assert.equal(origineDe("chrome://extensions"), null);
  assert.equal(origineDe("pas une url"), null);
  assert.equal(origineDe(undefined), null);
});

test("la traduction suit l'onglet sur la même origine seulement", () => {
  const s = { langue: "fr", origine: "https://a.test" };
  assert.equal(resteSuivi(s, "https://a.test/cours/page1.html"), true);
  assert.equal(resteSuivi(s, "https://b.test/"), false);
  assert.equal(resteSuivi(s, undefined), true);
  assert.equal(resteSuivi(s, "about:blank"), true);
});

test("décision : suivi, puis règle, puis proposition", () => {
  const suivi = { langue: "fr", origine: "https://a.test" };
  const arret = { ...suivi, arret: true };
  assert.deepEqual(decision(suivi, null, true, true), { langue: "fr" });
  assert.deepEqual(decision(suivi, { mode: "original" }, true, true), { langue: "fr" });
  assert.equal(decision(arret, { mode: "traduire", langue: "en" }, true, true), null);
  assert.deepEqual(decision(null, { mode: "traduire", langue: "en" }, false, false), { langue: "en" });
  assert.equal(decision(null, { mode: "original" }, true, true), null);
  assert.deepEqual(decision(null, null, true, true), { proposer: true });
  assert.equal(decision(null, null, true, false), null);
  assert.equal(decision(null, null, false, true), null);
});

test("langue par défaut : celle du navigateur si proposée, sinon français", () => {
  const dispo = ["fr", "en", "es"];
  assert.equal(langueParDefaut("en-US", dispo), "en");
  assert.equal(langueParDefaut("es", dispo), "es");
  assert.equal(langueParDefaut("ja", dispo), "fr");
  assert.equal(langueParDefaut("", dispo), "fr");
});
