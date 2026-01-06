import os
import sys
import time
from google import genai
from core.config import init_gemini
from core.tts import speak
from core.logger import log
from core.utils import timeit

# ================================================================
# GEMINI CONFIG
# ================================================================
summary_client = init_gemini()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

# ================================================================
# SUMMARY FUNCTION
# ================================================================
@timeit("[GEMINI SUMMARY]")
def summarize(text: str) -> str:
    """
    Summarizes a block of text using Gemini.
    Returns summary string.
    """
    
    if not text or len(text.strip()) == 0:
        return "No text provided."

    prompt = f"""
You are an AI summarizer. Summarize the following text clearly and concisely
without changing the meaning ({int(len(text) / 4)} words max):

TEXT:
\"\"\"{text}\"\"\"
"""

    t0 = time.time()

    try:
        response = summary_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
    except Exception as e:
        log("SUMMARY", "-", f"Gemini error: {e}")
        speak(f"Gemini error: {e}")
        return f"Gemini error: {e}"

    summary_text = getattr(response, "text", "")

    duration = round(time.time() - t0, 2)
    log("SUMMARY", "-", f"{len(summary_text)} chars in {duration}s")

    return summary_text

# ================================================================
# CLI MODE (python summarize.py "text here")
# ================================================================
if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("\nUsage:")
        print("   python -m core.summarize \"your text here\"")
        print("Or import summarize() inside another script.\n")
        sys.exit(0)

    input_text = " ".join(sys.argv[1:])
    output = summarize(input_text)

    print("\n===== SUMMARY =====\n")
    print(output)
    print("\n===================\n")
