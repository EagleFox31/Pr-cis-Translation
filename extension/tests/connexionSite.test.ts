import { test } from "node:test";
import assert from "node:assert/strict";
import { challengeDe, genererState, genererVerifier, lireRetour, urlAutorisation } from "../src/connexionSite.ts";

const SITE = "https://precis-translator.trigenys.com";

test("verifier : 43 caractères base64url, différent à chaque appel", () => {
  const a = genererVerifier();
  assert.match(a, /^[A-Za-z0-9_-]{43}$/);
  assert.notEqual(a, genererVerifier());
});

test("state : base64url d'au moins 16 caractères, différent à chaque appel", () => {
  const a = genererState();
  assert.match(a, /^[A-Za-z0-9_-]{16,128}$/);
  assert.notEqual(a, genererState());
});

test("challenge : vecteur de l'annexe B de la RFC 7636", async () => {
  assert.equal(
    await challengeDe("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"),
    "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
  );
});

test("challenge : 43 caractères pour un verifier généré", async () => {
  assert.match(await challengeDe(genererVerifier()), /^[A-Za-z0-9_-]{43}$/);
});

test("adresse d'autorisation", () => {
  const url = new URL(urlAutorisation(SITE, "chal-_", "etat-_"));
  assert.equal(url.origin, SITE);
  assert.equal(url.pathname, "/extension/autoriser");
  assert.equal(url.searchParams.get("challenge"), "chal-_");
  assert.equal(url.searchParams.get("state"), "etat-_");
});

test("retour : code et state lus dans le fragment", () => {
  assert.deepEqual(lireRetour(`${SITE}/extension/connecte#code=abc_-1&state=xyz`, SITE), { code: "abc_-1", state: "xyz" });
});

test("retour : refus de l'utilisateur", () => {
  assert.deepEqual(lireRetour(`${SITE}/extension/connecte#erreur=refus&state=xyz`, SITE), { erreur: "refus", state: "xyz" });
});

test("retour : page sans fragment, avec barre finale", () => {
  assert.deepEqual(lireRetour(`${SITE}/extension/connecte`, SITE), {});
  assert.deepEqual(lireRetour(`${SITE}/extension/connecte/#code=a`, SITE), { code: "a" });
});

test("retour : autre page ou autre origine ignorées", () => {
  assert.equal(lireRetour(`${SITE}/extension/autoriser?challenge=a&state=b`, SITE), null);
  assert.equal(lireRetour(`${SITE}/extension`, SITE), null);
  assert.equal(lireRetour(`https://autre.example/extension/connecte#code=a`, SITE), null);
  assert.equal(lireRetour(`${SITE}.autre.example/extension/connecte#code=a`, SITE), null);
  assert.equal(lireRetour(undefined, SITE), null);
  assert.equal(lireRetour("pas une adresse", SITE), null);
});
