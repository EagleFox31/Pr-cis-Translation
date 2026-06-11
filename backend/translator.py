import os
import httpx
import logging
from typing import List
from fastapi import HTTPException

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("translator")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# System prompt optimized for layout-preserving translations
SYSTEM_PROMPT = """You are a highly precise professional translator tool. 
Your goal is to translate the user text into the target language ({target_lang}).

CRITICAL REQUIREMENTS:
1. Preserve the exact structure, layout, paragraph spacing, and line breaks of the original text.
2. Retain any list bullet formatting, headers, or indentations.
3. Keep formatting tags (e.g., Markdown, HTML, special symbols) exactly as they are.
4. Translate the content accurately and naturally, maintaining the tone of the original document.
5. Do NOT add any conversational introduction, explanation, or commentary. Output ONLY the translated text.
"""

def split_text_into_chunks(text: str, max_chunk_size: int = 4000) -> List[str]:
    """Splits a long text into chunks of paragraphs to avoid LLM token limit issues."""
    paragraphs = text.split("\n")
    chunks = []
    current_chunk = []
    current_length = 0

    for paragraph in paragraphs:
        # +1 accounts for the newline character when joining
        if current_length + len(paragraph) + 1 > max_chunk_size:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_length = 0
        current_chunk.append(paragraph)
        current_length += len(paragraph) + 1

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


async def translate_chunk(client: httpx.AsyncClient, text_chunk: str, target_lang: str) -> str:
    """Translates a single chunk of text using DeepSeek API."""
    if not DEEPSEEK_API_KEY:
        logger.error("DEEPSEEK_API_KEY is not configured.")
        raise HTTPException(
            status_code=500,
            detail="DeepSeek API key is not configured on the server. Please add it to your environment variables."
        )

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT.format(target_lang=target_lang)},
            {"role": "user", "content": text_chunk}
        ],
        "temperature": 0.2,
        "max_tokens": 2048
    }

    try:
        response = await client.post(DEEPSEEK_API_URL, json=payload, headers=headers, timeout=60.0)
        
        if response.status_code != 200:
            logger.error(f"DeepSeek API returned error status {response.status_code}: {response.text}")
            raise HTTPException(
                status_code=502,
                detail=f"DeepSeek translation API error: {response.text}"
            )

        data = response.json()
        translated_text = data["choices"][0]["message"]["content"]
        return translated_text.strip()
    
    except httpx.RequestError as exc:
        logger.error(f"Network request to DeepSeek failed: {exc}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to reach DeepSeek translation server: {str(exc)}"
        )


async def translate_text(text: str, target_lang: str) -> str:
    """Translates full text, chunking if necessary to respect token/character limits."""
    if not text.strip():
        return ""

    chunks = split_text_into_chunks(text)
    translated_chunks = []

    async with httpx.AsyncClient() as client:
        for i, chunk in enumerate(chunks):
            logger.info(f"Translating chunk {i+1}/{len(chunks)} ({len(chunk)} characters)...")
            translated_chunk = await translate_chunk(client, chunk, target_lang)
            translated_chunks.append(translated_chunk)

    return "\n".join(translated_chunks)
