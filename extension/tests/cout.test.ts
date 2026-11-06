import { test } from "node:test";
import assert from "node:assert/strict";
import { messageAccord, messageLimiteImages } from "../src/lib/cout.ts";

test("pluriel", () => {
  assert.equal(
    messageAccord(3),
    "3 images avec du texte possible — jusqu'à 3 crédits (débit seulement si l'image est traduite)",
  );
});

test("singulier", () => {
  assert.equal(
    messageAccord(1),
    "1 image avec du texte possible — jusqu'à 1 crédit (débit seulement si l'image est traduite)",
  );
});

test("limite d'images", () => {
  assert.equal(messageLimiteImages(10, 23), "10 images sur 23 traduites — limite atteinte pour cette page");
  assert.equal(messageLimiteImages(1, 4), "1 image sur 4 traduite — limite atteinte pour cette page");
});
