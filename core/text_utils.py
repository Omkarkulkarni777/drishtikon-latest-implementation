# core/text_utils.py
# ================================================================
#  TEXT UTILITIES
#  - Sentence splitting with forgiving behavior for OCR'd text
# ================================================================

import re
from typing import List


def split_into_sentences(text: str, min_len: int = 10) -> List[str]:
    """
    Split text into 'forgiving' sentence chunks.

    Forgiving behavior:
    - Split on ., ?, ! followed by whitespace
    - Strip whitespace around each piece
    - Drop completely empty chunks
    - Merge very short fragments (len < min_len) into the previous sentence
      to reduce OCR-induced fragmentation.

    This is designed for noisy OCR text where:
    - Abbreviations (e.g., "Dr.", "Mr.") may appear
    - Line breaks or hyphenation may cause tiny fragments
    """
    if not text:
        return []

    # Basic split on sentence-ending punctuation + whitespace
    raw_chunks = re.split(r'(?<=[.!?])\s+', text)

    # Clean up whitespace and remove empties
    cleaned = [chunk.strip() for chunk in raw_chunks if chunk and chunk.strip()]

    if not cleaned:
        return []

    sentences: List[str] = []

    for chunk in cleaned:
        # If this is the first chunk, just add it
        if not sentences:
            sentences.append(chunk)
            continue

        # If the chunk is very short (likely OCR noise), merge into previous
        if len(chunk) < min_len:
            sentences[-1] = sentences[-1] + " " + chunk
        else:
            sentences.append(chunk)

    return sentences


if __name__ == "__main__":
    sample = (
        "This is a test. OCR text can be messy. "
        "Dr. Smith went to the U.S. in 2020. "
        "Short. Frags. Should merge."
    )
    for i, s in enumerate(split_into_sentences(sample), 1):
        print(f"{i}: {s}")
