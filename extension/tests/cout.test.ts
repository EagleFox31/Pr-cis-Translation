import { test } from "node:test";
import assert from "node:assert/strict";
import { messageAccord, messageLimiteImages } from "../src/lib/cout.ts";

test("pluriel", () => {
  assert.equal(
    messageAccord(3),
    "3 images à traduire — jusqu'à 3 crédits",
  );
});

test("singulier", () => {
  assert.equal(
    messageAccord(1),
    "1 image à traduire — jusqu'à 1 crédit",
  );
});

test("limite d'images", () => {
  assert.equal(messageLimiteImages(10, 23), "10 images sur 23 traduites — limite atteinte pour cette page");
  assert.equal(messageLimiteImages(1, 4), "1 image sur 4 traduite — limite atteinte pour cette page");
});
