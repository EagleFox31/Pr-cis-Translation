import { test } from "node:test";
import assert from "node:assert/strict";
import { messageAccord } from "../src/lib/cout.ts";

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
