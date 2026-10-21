"""Measure actual Office extraction text without translating or calling an API."""
from dataclasses import dataclass
import io
from pathlib import Path, PurePosixPath
import re
import tempfile
import zipfile

from engines import new_engine

FORMATS = ("pdf", "pptx", "docx", "xlsx")
DEFAULT_LIMITS = {"pdf": 20, "pptx": 20, "docx": 10_000, "xlsx": 10, "xlsx_words": 5_000}
UNIT_NAMES = {"pdf": "pages", "pptx": "slides", "docx": "words", "xlsx": "sheets"}


@dataclass(frozen=True)
class BetaCost:
    format: str
    units: int
    words: int = 0


def word_count(text: str) -> int:
    text = re.sub(r"\[\[/?\d+\]\]", "", text)
    # Unspaced CJK text must not become one unlimited "word".
    text = re.sub(r"([\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af])", r" \1 ", text)
    return sum(bool(re.search(r"[^\W\d_]", part)) for part in re.findall(
        r"[^\W_]+(?:['’\-][^\W_]+)*", text, flags=re.UNICODE))


def _texts(node):
    if isinstance(node, dict):
        if isinstance(node.get("text"), str):
            yield node["text"]
        for key, value in node.items():
            if key != "text" and isinstance(value, (dict, list)):
                yield from _texts(value)
    elif isinstance(node, list):
        for item in node:
            yield from _texts(item)


def office_cost(data: bytes, ext: str) -> BetaCost:
    if ext not in ("docx", "xlsx"):
        raise ValueError("Unsupported beta Office format")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 10_000 or sum(e.file_size for e in entries) > 128 * 1024 * 1024:
                raise ValueError("Le document décompressé est trop volumineux pour être traité.")
            for entry in entries:
                path = PurePosixPath(entry.filename.replace("\\", "/"))
                if path.is_absolute() or ".." in path.parts or entry.flag_bits & 1:
                    raise ValueError("Le conteneur Office n'est pas valide.")
        engine = new_engine(ext)
        if engine is None:
            raise ValueError("Ce format n'est pas disponible.")
        try:
            with tempfile.TemporaryDirectory(prefix="precis-beta-meter-") as folder:
                source = Path(folder) / f"source.{ext}"
                source.write_bytes(data)
                extraction, _ = engine.extract_text(str(source), str(Path(folder) / "text.json"))
                words = sum(word_count(text) for text in _texts(extraction))
                sheets = len(engine.feuilles()) if ext == "xlsx" else 0
        finally:
            if hasattr(engine, "_nettoyer"):
                engine._nettoyer()
            elif hasattr(engine, "_cleanup_temp"):
                engine._cleanup_temp()
        if words == 0:
            raise ValueError("Ce fichier ne contient pas de texte à traduire.")
        return BetaCost(ext, words if ext == "docx" else max(1, sheets), words if ext == "xlsx" else 0)
    except (ValueError, zipfile.BadZipFile) as error:
        if isinstance(error, zipfile.BadZipFile):
            raise ValueError("Le fichier Office n'est pas valide.") from error
        raise
    except Exception as error:
        raise ValueError("Impossible de compter le texte du document Office.") from error
