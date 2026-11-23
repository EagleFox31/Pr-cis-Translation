import { test } from "node:test";
import assert from "node:assert/strict";
import { creerIdPages } from "../src/lib/page.ts";

test("même identifiant pour une adresse, un neuf pour une autre", () => {
  let n = 0;
  const id = creerIdPages(() => `id${++n}`);
  assert.equal(id("https://a.test/1"), "id1");
  assert.equal(id("https://a.test/1"), "id1");
  assert.equal(id("https://a.test/2"), "id2");
});
