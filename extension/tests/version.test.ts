import { test } from "node:test";
import assert from "node:assert/strict";
import { plusRecente } from "../src/lib/version.ts";

test("version distante plus récente", () => {
  assert.equal(plusRecente("0.2.0", "0.1.0"), true);
  assert.equal(plusRecente("0.1.10", "0.1.9"), true);
  assert.equal(plusRecente("1", "0.9.9"), true);
  assert.equal(plusRecente("0.1.0.1", "0.1.0"), true);
});

test("même version ou plus ancienne", () => {
  assert.equal(plusRecente("0.1.0", "0.1.0"), false);
  assert.equal(plusRecente("0.1", "0.1.0"), false);
  assert.equal(plusRecente("0.1.0", "0.2.0"), false);
});

test("version illisible ignorée", () => {
  assert.equal(plusRecente("abc", "0.1.0"), false);
  assert.equal(plusRecente("", "0.1.0"), false);
});
