import os
import sys
import time
from dotenv import load_dotenv
import google.generativeai as genai
from core.tts import speak
from core.logger import log

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.utils import absolute_path, ensure_dir
from core.logger import log

load_dotenv()

# ================================================================
# GEMINI CONFIG
# ================================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")  # fallback

if not GEMINI_API_KEY:
    raise ValueError("Gemini API key missing. Set GEMINI_API_KEY in .env")

genai.configure(api_key=GEMINI_API_KEY)


# ================================================================
# SUMMARY FUNCTION
# ================================================================
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
    model = genai.GenerativeModel(GEMINI_MODEL)

    try:
        response = model.generate_content(prompt)
    except Exception as e:
        log("SUMMARY", "-", f"Gemini error: {e}")
        speak(f"Gemini error: {e}")
        return f"Gemini error: {e}"

    summary_text = getattr(response, "text", "")

    duration = round(time.time() - t0, 2)
    log("SUMMARY", "-", f"{len(summary_text)} chars in {duration}s")
    speak("Summary:")
    speak(summary_text)
    speak(f"{len(summary_text)} characters in {duration} seconds")

    return summary_text


# ================================================================
# CLI MODE (python summarize.py "text here")
# ================================================================
if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("\nUsage:")
        print("   python summarize.py \"your text here\"")
        print("Or import summarize() inside another script.\n")
        sys.exit(0)

    input_text = " ".join(sys.argv[1:])
    output = summarize(input_text)

    print("\n===== SUMMARY =====\n")
    print(output)
    print("\n===================\n")
