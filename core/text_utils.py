# core/text_utils.py
# ================================================================
# TEXT UTILITIES
# - Sentence splitting with forgiving behavior for OCR'd text
# ================================================================
import re
from typing import List
def split_into_sentences_rag(
    text: str,
    min_len: int = 80,
    max_len: int = 220,
) -> List[str]:
    """
    Split OCR text into speakable chunks for TTS.

    Design goals:
    - Prefer natural breaks after punctuation (.!?;)
    - Avoid very short chunks caused by OCR noise
    - Merge small fragments into the previous chunk
    - Keep chunks within a comfortable TTS length window

    This is NOT a linguistically correct sentence splitter.
    """

    if not text:
        return []
    
    text = text.translate(str.maketrans("", "", "\"'“”‘’*"))

    # Split after sentence-like punctuation, keep punctuation attached
    raw_chunks = re.split(r'(?<=[.!?;])', text)

    chunks = []
    for piece in raw_chunks:
        piece = piece.strip()
        if not piece:
            continue

        if (
            chunks
            and len(piece) < min_len
            and len(chunks[-1]) + len(piece) <= max_len
        ):
            chunks[-1] += " " + piece
        else:
            chunks.append(piece)

    return chunks

def split_into_sentences(text):
    raw_chunks = text.split("SENT_GRP")
    chunks = []
    for piece in raw_chunks:
        piece = piece.strip()
        if not piece:
            continue
        piece = piece.replace('\n', '...')
        chunks.append(piece)
    return chunks
if __name__ == "__main__":
    sample = (
    "This is a test. OCR text can be messy. "
    "Dr. Smith went to the U.S. in 2020. "
    "Short. Frags. Should merge."
    )
    for i, s in enumerate(split_into_sentences(sample), 1):
        print(f"{i}: {s}")