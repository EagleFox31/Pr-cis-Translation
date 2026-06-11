import os
import io
from fastapi import HTTPException

# Attempt imports for docx and pdf, standard error if missing when executing
try:
    import docx
except ImportError:
    docx = None

try:
    import pypdf
except ImportError:
    pypdf = None


def extract_text_from_txt(file_bytes: bytes) -> str:
    """Extracts text from a plain text file."""
    for encoding in ("utf-8", "latin-1", "utf-16"):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=400, detail="Could not decode text file with standard encodings.")


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extracts text from a DOCX file."""
    if docx is None:
        raise HTTPException(
            status_code=500,
            detail="python-docx library is not installed on the server. Cannot process DOCX files."
        )
    try:
        doc = docx.Document(io.BytesIO(file_bytes))
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return "\n".join(full_text)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse DOCX file: {str(e)}")


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extracts text from a PDF file."""
    if pypdf is None:
        raise HTTPException(
            status_code=500,
            detail="pypdf library is not installed on the server. Cannot process PDF files."
        )
    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        full_text = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                full_text.append(text)
        return "\n\n".join(full_text)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse PDF file: {str(e)}")


def extract_text(filename: str, file_bytes: bytes) -> str:
    """Routes the file to the correct text extractor based on its extension."""
    ext = filename.split(".")[-1].lower()
    if ext == "txt":
        return extract_text_from_txt(file_bytes)
    elif ext == "docx":
        return extract_text_from_docx(file_bytes)
    elif ext == "pdf":
        return extract_text_from_pdf(file_bytes)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension: .{ext}. Only .txt, .pdf, and .docx are supported."
        )
