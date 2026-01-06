import os
import sys
import time

from core.tts import speak
from core.logger import log
from core.config import init_gemini
from core.utils import timeit

# ================================================================
# GEMINI CONFIG
# ================================================================
query_client = init_gemini()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

# ================================================================
# QUERY FUNCTION
# ================================================================
@timeit("[GEMINI QUERY RESOLUTION]")
def answer_query(text: str, question: str) -> str:
    """
    Answers from a block of text using Gemini.
    Returns answer string.
    """
    
    if not text or len(text.strip()) == 0:
        return "No text provided."

    prompt = f"""
You are a query resolver.
The user has asked: {question}

Answer the question clearly and concisely
by referring to the following text only, in less than 50 words.

TEXT:
\"\"\"{text}\"\"\"
"""

    t0 = time.time()

    try:
        response = query_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
    except Exception as e:
        log("ANSWER", "-", f"Gemini error: {e}")
        speak(f"Gemini error: {e}")
        return f"Gemini error: {e}"

    answer_text = getattr(response, "text", "")

    duration = round(time.time() - t0, 2)
    log("ANSWER", "-", f"{len(answer_text)} chars in {duration}s")

    return answer_text
