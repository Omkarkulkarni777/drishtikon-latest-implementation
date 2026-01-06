import os
import cv2
import io
import time
import threading
import tkinter as tk
from tkinter import filedialog
from PIL import Image
from dotenv import load_dotenv
from google import genai

from core.stt import listen_continuous
from core.stt_commands import helper_for_exit
from core.utils import absolute_path, ensure_dir, load_credential_path, timeit
from core.tts import speak
from core.tts_player import tts_main
from core.playback_controls import play, non_blocking_play, wait_for_key
from core.prompts import (
    select_file_p,
    generating_answer_p,
    exiting_detection_module_p,
    ask_query_intro_p,
)

load_dotenv()

# --------------------------------------------------
# ROUTED BUTTON EVENT (NO GPIO)
# --------------------------------------------------
BUTTON_FILE = "/tmp/detection_button"

def poll_button_event():
    if os.path.exists(BUTTON_FILE):
        os.remove(BUTTON_FILE)
        return "v"
    return None

# ================================================================
# GEMINI CONFIG (NEW SDK)
# ================================================================
load_credential_path("detection", "detect-key.json")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set")

# Create ONE client
client = genai.Client(api_key=GEMINI_API_KEY)

# ================================================================
# GEMINI PROMPT (VERY IMPORTANT)
# ================================================================
GEMINI_SCENE_PROMPT = """
You are assisting a visually impaired user.
Describe only what requires attention right now.
Focus on obstacles, people, vehicles, or hazards.
Be concise and calm.
"""

@timeit("[DUMMY DETECTION GEMINI SCENE SUMMARY]")
def gemini_scene_summary(image_path: str, user_query: str = None) -> str:
    img = Image.open(image_path)

    if img.mode == "RGBA":
        img = img.convert("RGB")

    img.thumbnail((1600, 1600))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=75)

    if not user_query:
        user_query = GEMINI_SCENE_PROMPT

    user_query += (
        "\nIMAGE DOES NOT HAVE THE USER. "
        "IT IS TAKEN BY THE USER. "
        "IT IS NOT A SELFIE. "
        "DO NOT include asterisks, quotes, or any formatting. "
        "LESS THAN 60 WORDS."
    )

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {"mime_type": "image/jpeg", "data": buf.getvalue()},
                        {"text": user_query},
                    ],
                }
            ],
        )
    except Exception as e:
        return f"Gemini error: {e}"

    return getattr(response, "text", "I could not understand the scene.")

# ================================================================
# MAIN LOOP
# ================================================================
@timeit("[DUMMY DETECTION MAIN]")
def main():
    ensure_dir(absolute_path("results", "gemini_cache"))
    
    # ------------------------------------------------------------
    # Image selection
    # ------------------------------------------------------------
    cam = cv2.VideoCapture(0)

    print("\n[v] Ask query | [v (and say 'exit')] Quit\n")

    while True:
        # --------------------------------------------------------
        # Wait for user intent
        # --------------------------------------------------------
        key = None
        while key is None:
            key = poll_button_event()
            time.sleep(0.05)
        # --------------------------------------------------------
        # Gemini summary
        # --------------------------------------------------------
        if key == "v":
            # --------------------------------------------------------
            # Capture frame if camera is active
            # --------------------------------------------------------
            if cam:
                ret, frame = cam.read()
                if not ret:
                    break

                img_path = absolute_path("results", "gemini_cache", "live.jpg")

            try:
                cv2.imwrite(img_path, frame)
                play(tts_main, ask_query_intro_p)

                user_query = listen_continuous()
                if helper_for_exit(user_query) == "q" or len(user_query.split()) < 2:
                    play(tts_main, exiting_detection_module_p)
                    break

                play(tts_main, generating_answer_p)

                text = gemini_scene_summary(img_path, user_query)
                audio_path = speak(text)

                non_blocking_play(
                    tts_main,
                    audio_path,
                    module_name="detection",
                    cmd_to_stop_audio_file="Press 's' to stop description",
                )

            except Exception as e:
                print(f"[Gemini Error] {e}")

        # --------------------------------------------------------
        # Exit
        # --------------------------------------------------------
        else:
            play(tts_main, exiting_detection_module_p)
            break

    if cam:
        cam.release()

# ================================================================
if __name__ == "__main__":
    main()
