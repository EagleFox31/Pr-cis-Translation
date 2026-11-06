import { test } from "node:test";
import assert from "node:assert/strict";
import { origineDe, resteSuivi } from "../src/lib/suivi.ts";

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
  assert.equal(resteSuivi(s, undefined), false);
});
