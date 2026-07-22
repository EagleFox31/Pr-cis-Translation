"""Aides pures autour des fichiers envoyes et des selections de pages.

Aucune de ces fonctions ne touche au disque, au reseau ni a la base : elles
transforment une valeur en une autre. C'est ce qui les rend testables seules et
reutilisables par les routes comme par les executeurs de traduction.
"""
from __future__ import annotations

import hashlib
import os


def get_file_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()[:12]

def sanitize_filename(name: str) -> str:
    stem = os.path.splitext(name)[0]
    cleaned = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in stem)
    cleaned = "_".join(cleaned.split())
    return cleaned[:50] or "document"

def parse_page_range(s: str):
    """Convertit une saisie de plage de pages ('1-5, 8, 11-13') en un ensemble
    de numéros 1-basés {1,2,3,4,5,8,11,12,13}. Retourne None si vide
    (= toutes les pages). Les jetons invalides sont ignorés silencieusement."""
    if not s or not s.strip():
        return None
    pages: set[int] = set()
    for tok in s.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if "-" in tok:
            a, _, b = tok.partition("-")
            try:
                a, b = int(a.strip()), int(b.strip())
            except ValueError:
                continue
            if a > b:
                a, b = b, a
            for p in range(a, b + 1):
                if p >= 1:
                    pages.add(p)
        else:
            try:
                p = int(tok)
            except ValueError:
                continue
            if p >= 1:
                pages.add(p)
    return pages or None

def pages_token(pages_set) -> str:
    """Jeton de cache déterministe pour une sélection de pages. Lisible quand la
    sélection est une plage contiguë ('p3-5', 'p7'), sinon un hash court. Vide
    si aucune sélection (préserve les caches existants 'toutes les pages')."""
    if not pages_set:
        return ""
    sp = sorted(pages_set)
    if sp == list(range(sp[0], sp[-1] + 1)):
        return f"p{sp[0]}" if sp[0] == sp[-1] else f"p{sp[0]}-{sp[-1]}"
    return "p" + hashlib.sha1(",".join(map(str, sp)).encode()).hexdigest()[:8]
